import os
import multiprocessing as mp
import math
import logging
import queue
import threading
from pathlib import Path
import click
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import MofNCompleteColumn
from rich.progress import TextColumn
from rich.progress import BarColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn
import yaml
from . import config_utilities as cfu
from . import dict_utils as dctu
from .gen_configurations import pipelined_generate_patches
from .gen_configurations import pipelined_generate_full_run_config
from .gen_configurations import generate_tool_configurations
from .acquire_data import pipelined_acquire_data
from .postprocessing_queue import unpack_data, frack_data


_log_level_dict = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


@click.command()
@click.argument("config", type=click.Path(exists=True), metavar="[ROOT CONFIG FILE]")
@click.argument(
    "netcfg", type=click.Path(exists=True), metavar="[NERTWORK CONFIG FILE]"
)
@click.argument("procedure", type=str, metavar="[PROCEDURE NAME]")
@click.argument(
    "output_dir", type=click.Path(dir_okay=True), metavar="[OUTPUT DIRECTORY]"
)
@click.option(
    "--log",
    "-l",
    type=str,
    default="daq.log",
    help="Enable logging and append logs to the filename passed to " "this option",
)
@click.option(
    "--loglevel",
    "-v",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
)
@click.option(
    "--root/--no-root",
    default=False,
    help="keep the rootfile generated as intermediary",
)
@click.option(
    "--full_conf_generators",
    "-f",
    type=int,
    default=2,
    help="set how many full-cfg generators to run, default 1",
)
@click.option(
    "--unpack_tasks",
    "-u",
    default=2,
    type=int,
    help="number of unpackers/frackers to run in parallel",
)
@click.option(
    "--frack_tasks",
    "-f",
    default=7,
    type=int,
    help="number of unpackers/frackers to run in parallel",
)
@click.option(
    "--compression",
    "-c",
    default=2,
    type=int,
    help="Set the compression for the hdf file, 0 = no compression"
    " 9 = best compression",
)
@click.option(
    "--keep/--no-keep",
    default=False,
    help="Keep the already aquired data, defaults to False",
)
@click.option(
    "--readback/--no-readback",
    default=False,
    help="Tell the sc-server to read back the register value" "written to the roc",
)
@click.option(
    "--full-readback/-no-full-readback",
    default=False,
    help="Enable a Full read of the ROC parameters after every run",
)
def main(
    config,
    netcfg,
    procedure,
    output_dir,
    log,
    loglevel,
    root,
    full_conf_generators,
    unpack_tasks,
    frack_tasks,
    compression,
    keep,
    readback,
    full_readback,
):
    config = click.format_filename(config)
    # generate the conifgurations
    if log:
        logging.basicConfig(
            filename="full-daq.log",
            level=loglevel,
            format="[%(asctime)s] %(levelname)-10s:" "%(name)-50s %(message)s",
        )
    config = click.format_filename(config)
    try:
        procedure, (
            system_default_config,
            system_init_config,
            run_configs,
            run_count,
        ) = cfu.get_procedure_configs(
            main_config_file=config,
            procedure_name=procedure,
            calibration=None,
            diff=True,
        )
    except ValueError as err:
        print(f"The procedure with name: {err.args[1]} could not be found,")
        print("Available procedures are:")
        for pname in err.args[2]:
            print(f"\t {pname}")
        exit(1)

    # create the output directory and the initial files
    output_dir = Path(output_dir)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    generate_tool_configurations(
        output_dir, netcfg, procedure, system_default_config, system_init_config
    )
    with open(netcfg, "r", encoding="utf-8") as nw_file:
        network_config = yaml.safe_load(nw_file.read())

    # get the data needed for the postprocessing
    raw_data = procedure["mode"] == "full"
    data_columns = procedure["data_columns"]
    try:
        data_format = procedure["data_format"]
    except KeyError:
        data_format = "raw"
    characterisation_mode = data_format == "characterisation"

    # generate the configurations for the runs
    num_digits = math.ceil(math.log(run_count, 10))
    full_config = dctu.update_dict(system_default_config, system_init_config)

    # event telling all the subprocesses to stop
    stop = mp.Event()

    # queue that holds the filenames for a run indicating the
    # run config has been generated
    patch_gen_out_full_gen_in = queue.Queue()
    patch_gen_progress_queue = queue.Queue()
    patch_gen_done = threading.Event()

    # queues and signals relating to the full config generation
    fcm = mp.Manager()
    full_gen_out_daq_in = fcm.Queue()
    full_config_gen_progress = fcm.Queue()
    full_config_gen_done = threading.Event()

    # daq
    daq_out_unpack_in = queue.Queue()
    daq_progress = queue.Queue()
    daq_done = threading.Event()
    daq_active = False
    daq_system_initialized = threading.Event()

    # unpacking
    unpack_out_frack_in = queue.Queue()
    unpack_progress = queue.Queue()
    unpack_done = threading.Event()

    # fracking
    frack_progress = queue.Queue()
    fracking_done = threading.Event()

    config_gen_thread = threading.Thread(
        target=pipelined_generate_patches,
        args=(
            output_dir,  # directory to place the
            run_configs,
            patch_gen_out_full_gen_in,
            patch_gen_progress_queue,
            patch_gen_done,
            num_digits,
            stop,
        ),
    )
    full_config_gen_thread = threading.Thread(
        target=pipelined_generate_full_run_config,
        args=(
            patch_gen_done,
            patch_gen_out_full_gen_in,
            full_config,
            full_gen_out_daq_in,
            full_config_gen_progress,
            full_config_gen_done,
            full_conf_generators,
            stop,
        ),
    )
    # acquire the data in a separate thread
    daq_thread = threading.Thread(
        target=pipelined_acquire_data,
        args=(
            full_gen_out_daq_in,
            daq_progress,
            daq_out_unpack_in,
            full_config_gen_done,
            daq_system_initialized,
            daq_done,
            stop,
            network_config,
            system_init_config,
            output_dir,
            keep,
            readback,
            procedure["run_start_tdc_procedure"],
            full_readback,
        ),
    )

    # start the unpack_tasks that turn the raw data into the root file
    unpack_thread = threading.Thread(
        target=unpack_data,
        args=(
            daq_out_unpack_in,
            unpack_progress,
            unpack_out_frack_in,
            daq_done,
            unpack_done,
            max(1, unpack_tasks),
            raw_data,
            characterisation_mode,
        ),
    )

    # frack the data (last step)
    frack_thread = threading.Thread(
        target=frack_data,
        args=(
            unpack_out_frack_in,
            frack_progress,
            unpack_done,
            fracking_done,
            max(1, frack_tasks),
            raw_data,
            root,
            compression,
            data_columns,
        ),
    )
    config_gen_thread.start()
    full_config_gen_thread.start()
    daq_thread.start()
    unpack_thread.start()
    frack_thread.start()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        run_config_progress_bar = progress.add_task(
            "Generating run configurations", total=run_count
        )
        full_config_progress_bar = progress.add_task(
            "Generating full config for fracker", total=run_count
        )
        daq_progbar = progress.add_task(
            "Acquiring Data from the Test System", total=run_count, start=False
        )
        unpack_progress_bar = progress.add_task("Unpacking data", total=run_count)
        frack_progress_bar = progress.add_task("fracking data", total=run_count)
        while not fracking_done.is_set():
            try:
                _ = patch_gen_progress_queue.get(block=False)
                progress.update(run_config_progress_bar, advance=1)
            except queue.Empty:
                pass
            try:
                _ = full_config_gen_progress.get(block=False)
                progress.update(full_config_progress_bar, advance=1)
            except queue.Empty:
                pass
            if daq_system_initialized.is_set() and not daq_active:
                progress.start_task(daq_progbar)
                daq_active = True
            try:
                if daq_active:
                    _ = daq_progress.get(block=False)
                    progress.update(daq_progbar, advance=1)
            except queue.Empty:
                pass
            try:
                _ = unpack_progress.get(block=False)
                progress.update(unpack_progress_bar, advance=1)
            except queue.Empty:
                pass
            try:
                _ = frack_progress.get(block=False)
                progress.update(frack_progress_bar, advance=1)
            except queue.Empty:
                pass
        progress.refresh()
    config_gen_thread.join()
    full_config_gen_thread.join()
    daq_thread.join()
    unpack_thread.join()
    frack_thread.join()
