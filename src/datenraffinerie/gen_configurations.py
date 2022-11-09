import os
import sys
import math
import shutil
from pathlib import Path
import threading
import multiprocessing as mp
import queue
import logging
from operator import and_
from functools import reduce
from copy import deepcopy
from typing import Iterator, Tuple
import click
import yaml
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import MofNCompleteColumn
from rich.progress import TextColumn
from rich.progress import BarColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn
from . import config_utilities as cfu
from . import dict_utils as dctu

_log_level_dict = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def generate_tool_configurations(
    output_dir: Path,
    network_config: Path,
    procedure: dict,
    system_default_config: dict,
    system_init_config: dict,
) -> None:
    """
    Create the configurations that govern the behaviour of the tools along with
    the initial state configurations of the system
    """
    init_config_path = output_dir / "initial_state_config.yaml"
    default_config_path = output_dir / "default_config.yaml"
    post_config_path = output_dir / "postprocessing_config.yaml"
    daq_config_path = output_dir / "daq_config.yaml"
    proc_network_config = output_dir / "network_config.yaml"
    procedure_config_files = [
        init_config_path,
        default_config_path,
        post_config_path,
        daq_config_path,
    ]
    # clean the output directory of any previous configuration files
    for file in procedure_config_files:
        if file.exists():
            os.remove(file)
    # generate the initial, default and network configuration
    shutil.copyfile(network_config, proc_network_config)
    with open(default_config_path, "w+", encoding="utf-8") as dcf:
        dcf.write(yaml.safe_dump(system_default_config))
    with open(init_config_path, "w+", encoding="utf-8") as icf:
        icf.write(yaml.safe_dump(system_init_config))
    with open(post_config_path, "w+", encoding="utf-8") as pcf:
        post_config = {}
        post_config["data_columns"] = procedure["data_columns"]
        post_config["mode"] = procedure["mode"]
        post_config["procedure"] = procedure["name"]
        post_config["data_format"] = procedure["data_format"]
        pcf.write(yaml.safe_dump(post_config))
    with open(daq_config_path, "w+", encoding="utf-8") as daqcf:
        daq_config = {}
        daq_config["run_start_tdc_procedure"] = procedure["run_start_tdc_procedure"]
        daqcf.write(yaml.safe_dump(daq_config))
    return


def generate_run_file_names(
    run_id: int, width: int, output_dir: Path
) -> Tuple[Path, Path, Path, Path, Path]:
    """
    Generate the file names for all the files of the run
    """
    run_conf_file_name = f"run_{run_id:0>{width}}_config.yaml"
    full_run_conf_file_name = f"run_{run_id:0>{width}}_config_full.yaml"
    raw_file_name = f"run_{run_id:0>{width}}_data.raw"
    root_file_name = f"run_{run_id:0>{width}}_data.root"
    hdf_file_name = f"run_{run_id:0>{width}}_data.h5"
    run_conf_path = output_dir / run_conf_file_name
    raw_file_path = output_dir / raw_file_name
    root_file_path = output_dir / root_file_name
    hdf_file_path = output_dir / hdf_file_name
    full_run_conf_path = output_dir / full_run_conf_file_name
    return (
        run_conf_path,
        full_run_conf_path,
        raw_file_path,
        root_file_path,
        hdf_file_path,
    )


def write_patch_to_file(
    config: dict, filenames: Tuple[Path, Path, Path, Path, Path]
) -> Tuple[dict, Tuple[Path, Path, Path, Path, Path]]:
    """
    Write the patch to a file and return what was
    passed in to act as a map function with side effects
    """
    with open(filenames[0], "w+", encoding="utf-8") as patch_file:
        patch_file.write(yaml.safe_dump(config))
    return (config, filenames)


def pipelined_generate_patches(
    output_dir: Path,
    run_configs: Iterator,
    patch_out_ful_config_in_queue: queue.Queue,
    config_gen_progress_queue: queue.Queue,
    patch_gen_done: threading.Event,
    num_digits: int,
    stop: threading.Event,
):
    """
    Generate the files in the output_dir that contain the patches
    that are applied to the system and pass the patch + the run file names down
    the queue
    """
    patch_generation_pipeline = map(
        lambda x: write_patch_to_file(*x),
        map(
            lambda x: (x[1], generate_run_file_names(x[0], num_digits, output_dir)),
            enumerate(run_configs),
        ),
    )
    for filepath_set in patch_generation_pipeline:
        if stop.is_set():
            break
        patch_out_ful_config_in_queue.put(filepath_set)
        config_gen_progress_queue.put(1)
    patch_gen_done.set()


def write_out_full_config(
    full_config: dict,
    run_file_paths: Tuple[Path, Path, Path, Path, Path],
    config_out_queue: mp.Queue,
    config_progress_queue: mp.Queue,
) -> None:
    """
    Write the output of the full config to a file and write signal
    to the queues that this has been done
    """
    with open(run_file_paths[1], "w+", encoding="utf-8") as out_file:
        out_file.write(yaml.safe_dump(full_config))
    config_out_queue.put(run_file_paths)
    config_progress_queue.put(1)


def full_config_param_generator(
    patch_gen_done: threading.Event,
    full_config: dict,
    run_config_and_files: queue.Queue,
    counfig_out_queue: mp.Queue,
    config_gen_progress_queue: mp.Queue,
    stop: threading.Event,
):
    """
    transform the queue of the patch write thread into a generator and
    keep track of the state of the config that is to be written out
    """
    current_config = deepcopy(full_config)
    while not patch_gen_done.is_set() or not run_config_and_files.empty():
        config, run_files = run_config_and_files.get()
        current_config = dctu.update_dict(current_config, config, in_place=True)
        yield (
            current_config,
            run_files,
            counfig_out_queue,
            config_gen_progress_queue,
        )
        if stop.is_set():
            break


def pipelined_generate_full_run_config(
    patch_gen_done: threading.Event,
    patch_gen_out_queue: queue.Queue,
    full_config: dict,
    full_conf_gen_out_daq_in_queue: mp.Queue,
    config_gen_progress_queue: mp.Queue,
    full_conf_gen_done: mp.Event,
    num_generators: int,
    stop: mp.Event,
):
    """
    Produce the full config and write it onto disk in parallel to
    speed up the process
    """
    with mp.Pool(num_generators) as config_gen_pool:
        config_gen_pool.starmap(
            write_out_full_config,
            full_config_param_generator(
                patch_gen_done,
                full_config,
                patch_gen_out_queue,
                full_conf_gen_out_daq_in_queue,
                config_gen_progress_queue,
                stop,
            ),
        )
    full_conf_gen_done.set()


@click.command()
@click.argument(
    "config", type=click.Path(exists=True), metavar="[main configuration file]"
)
@click.argument("netcfg", type=click.Path(exists=True))
@click.argument(
    "procedure", type=str, metavar="[Procedure to be run by the datenraffinerie]"
)
@click.argument(
    "output_dir",
    type=click.Path(dir_okay=True),
    metavar="[Location to write the configuration files to]",
)
@click.option(
    "--full_conf_generators",
    "-f",
    type=int,
    default=1,
    help="set how many full-cfg generators to run, default 1",
)
@click.option("--log/--no-log", type=bool, default=True, help="Enable/Disable logging")
@click.option(
    "--loglevel",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="specify the logging verbosity",
)
def generate_configuratons(
    config, netcfg, procedure, output_dir, full_conf_generators, log, loglevel
):
    # generate the conifgurations
    if log:
        logging.basicConfig(
            filename="gen_config.log",
            level=loglevel,
            format="[%(asctime)s] %(levelname)s:" "%(name)-50s %(message)s",
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
        sys.exit(1)

    # create the output directory and the initial files
    output_dir = Path(output_dir)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    generate_tool_configurations(
        output_dir, netcfg, procedure, system_default_config, system_init_config
    )

    # generate the configurations for the runs
    num_digits = math.ceil(math.log(run_count, 10))
    full_config = dctu.update_dict(system_default_config, system_init_config)

    # queues that hold the ouptut of the patch generator thread
    patch_gen_out_full_gen_in = queue.Queue()
    patch_gen_progress_queue = queue.Queue()
    patch_gen_done = threading.Event()

    # generate the starting config for multiple full_conf generators
    fcm = mp.Manager()
    full_configs_generated = fcm.Queue()
    full_config_generation_progress = fcm.Queue()
    full_config_generation_done = threading.Event()

    # global signals
    stop = mp.Event()

    config_gen_thread = threading.Thread(
        target=pipelined_generate_patches,
        args=(
            output_dir,
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
            full_configs_generated,
            full_config_generation_progress,
            full_config_generation_done,
            full_conf_generators,
            stop,
        ),
    )
    config_gen_thread.start()
    full_config_gen_thread.start()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        run_progress_bar = progress.add_task(
            "Generating run configurations", total=run_count
        )
        full_progress_bar = progress.add_task(
            "Generating full config for fracker", total=run_count
        )
        while (
            not full_config_generation_done.is_set()
            or not full_config_generation_progress.empty()
        ):
            while True:
                try:
                    _ = patch_gen_progress_queue.get(block=False)
                    progress.update(run_progress_bar, advance=1)
                except queue.Empty:
                    break
            while True:
                try:
                    _ = full_configs_generated.get(block=False)
                except queue.Empty:
                    break
            while True:
                try:
                    _ = full_config_generation_progress.get(block=False)
                    progress.update(full_progress_bar, advance=1)
                except queue.Empty:
                    break
            logging.debug(
                f"{full_config_generation_done.is_set()}"
                " = state of full config generator"
            )
        progress.refresh()
    config_gen_thread.join()
    full_config_gen_thread.join()
