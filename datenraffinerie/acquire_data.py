from pathlib import Path
import logging
import sys
import queue
import threading
import click
import yaml
from rich.progress import Progress
from rich.progress import MofNCompleteColumn, SpinnerColumn
from rich.progress import TextColumn, BarColumn
from rich.progress import TimeRemainingColumn, TimeElapsedColumn
from .daq_coordination import DAQCoordClient
from .gen_configurations import generate_run_file_names


_log_level_dict = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def pipelined_acquire_data(
    full_config_out: queue.Queue,
    data_acquisition_progress: queue.Queue,
    acquired_data: queue.Queue,
    full_conf_gen_done: threading.Event,
    daq_initialized: threading.Event,
    daq_done: threading.Event,
    stop: threading.Event,
    network_configuration: dict,
    initial_config: dict,
    output_dir: Path,
    keep: bool,
    readback: bool,
    start_tdcs: bool,
    full_readback: bool,
):
    # info needed for the generation of the filenames
    logger = logging.getLogger("data-acquisitor")
    logger.info("Connecting to DAQ-server")
    daq_system = DAQCoordClient(network_configuration)
    logger.info("Initializing DAQ-server")
    daq_system.initialize(initial_config, start_tdcs=start_tdcs)
    daq_initialized.set()
    logger.info("DAQ-System initialized")
    i = 0
    while (
        not full_conf_gen_done.is_set() or not full_config_out.empty()
    ) and not stop.is_set():
        run_config, file_names = full_config_out.get()
        raw_file_path = file_names[2]
        full_roc_readback_file_path = file_names[-1]
        if not keep or (keep and not raw_file_path.exists()):
            logger.info(f"gathering Data for run {i}")
            try:
                data = daq_system.measure(run_config, readback=readback)
            except ValueError as err:
                click.echo("An error ocurred during a measurement: " f"{err.args[0]}")
                del daq_system
                daq_done.set()
                return
            with open(raw_file_path, "wb+") as rdf:
                rdf.write(data)
            if full_readback:
                try:
                    config = daq_system.read_target(config=None)
                except ValueError as err:
                    click.echo(
                        "An error occured during readout of the target:"
                        f" {err.args[0]}"
                    )
                    del daq_system
                    daq_done.set()
                    return
                with open(full_roc_readback_file_path, "w+") as frcf:
                    frcf.write(yaml.safe_dump(config))
        else:
            logger.info(f"found existing data for run {i}, " "skipping acquisition")
        logger.info(f"data acquisition for run {i} done")
        logger.info(f"There are still {full_config_out.qsize()} " "items in the Queue")
        data_acquisition_progress.put(i)
        acquired_data.put(file_names)
        i += 1
    if stop.is_set():
        logger.info("Stop signal set, exiting")
    del daq_system
    daq_done.set()


@click.command()
@click.argument(
    "output_directory", type=click.Path(dir_okay=True), metavar="[OUTPUT DIR]"
)
@click.option(
    "--log",
    default="daq.log",
    type=str,
    help="Enable logging by specifying the output logfile",
)
@click.option(
    "--loglevel",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="specify the logging verbosity",
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
def pipelined_main(output_directory, log, loglevel, keep, readback, full_readback):
    logging.basicConfig(
        filename=log,
        level=_log_level_dict[loglevel],
        format="[%(asctime)s] %(levelname)s:" "%(name)-50s %(message)s",
    )
    logger = logging.getLogger("main")
    logger.info("Reading in configurations")
    # get the expected files from the directory
    output_directory = Path(output_directory)
    daq_config = output_directory / "daq_config.yaml"
    if not daq_config.exists():
        print(f"No daq_config.yaml found in {output_directory}" "exiting ...")
        sys.exit(1)
    with open(daq_config, "r", encoding='utf-8') as daqcf:
        daq_config = yaml.safe_load(daqcf.read())
    network_config = output_directory / "network_config.yaml"
    if not network_config.exists():
        print(f"No network_config.yaml found in {output_directory}" "exiting ...")
        sys.exit(1)
    with open(network_config, "r", encoding='utf-8') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    default_config = output_directory / "default_config.yaml"
    if not default_config.exists():
        print(f"No default_config.yaml found in {output_directory}" "exiting ...")
        sys.exit(1)
    with open(default_config, "r", encoding='utf-8') as dcf:
        default_config = yaml.safe_load(dcf.read())
    init_config = output_directory / "initial_state_config.yaml"
    if not init_config.exists():
        print(f"No initial_state_config.yaml found in {output_directory}" "exiting ...")
        sys.exit(1)
    with open(init_config, "r", encoding='utf-8') as icf:
        init_config = yaml.safe_load(icf.read())

    run_config_files = sorted(list(output_directory.glob("run_*_config.yaml")))
    num_digits = len(run_config_files[0].name.split("_")[1])
    run_count = len(run_config_files)
    run_ids = iter(range(len(run_config_files)))

    # read in the configurations
    # set up the different events that we are looking for
    full_gen_done = threading.Event()
    daq_system_initialized = threading.Event()
    daq_done = threading.Event()
    stop = threading.Event()

    # set up the queues to pass the data around
    full_gen_out_daq_in = queue.Queue()
    daq_progress_queue = queue.Queue()
    daq_out_unpack_in = queue.Queue()
    daq_thread = threading.Thread(
        target=pipelined_acquire_data,
        args=(
            full_gen_out_daq_in,
            daq_progress_queue,
            daq_out_unpack_in,
            full_gen_done,
            daq_system_initialized,
            daq_done,
            stop,
            network_config,
            init_config,
            output_directory,
            keep,
            readback,
            daq_config["run_start_tdc_procedure"],
            full_readback,
        ),
    )
    daq_thread.start()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            read_configurations = progress.add_task(
                "[cyan] Read run configurations from disk", total=run_count
            )
            daq_progbar = progress.add_task(
                "[turquoise] Acquiring Data from the Test System",
                total=run_count,
                start=False,
            )
            daq_active = False
            while not daq_done.is_set():
                # activate the progress bar when daq is initialized
                if daq_system_initialized.is_set() and not daq_active:
                    progress.start_task(daq_progbar)
                    daq_active = True
                try:
                    run_id = next(run_ids)
                    run_files = generate_run_file_names(
                        run_id, num_digits, output_directory
                    )
                    with open(run_files[0], "r", encoding="utf-8") as patchfile:
                        patch = yaml.safe_load(patchfile.read())
                    full_gen_out_daq_in.put((patch, run_files))
                    progress.update(read_configurations, advance=1)
                except StopIteration:
                    full_gen_done.set()
                    pass
                try:
                    _ = daq_progress_queue.get(block=False)
                    progress.update(daq_progbar, advance=1)
                except queue.Empty:
                    pass
                try:
                    _ = daq_out_unpack_in.get(block=False)
                except queue.Empty:
                    pass
    except KeyboardInterrupt:
        stop.set()
    daq_thread.join()
