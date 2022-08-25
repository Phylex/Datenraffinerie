from .daq_coordination import DAQCoordClient
import yaml
import glob
import click
from pathlib import Path
import logging
import os
import queue
import threading
import math
from rich.progress import Progress
from rich.progress import MofNCompleteColumn, SpinnerColumn
from rich.progress import TextColumn, BarColumn
from rich.progress import TimeRemainingColumn, TimeElapsedColumn


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command()
@click.argument('output_directory', type=click.Path(dir_okay=True),
                metavar='[directory containing the run configurations]')
@click.option('--log', default=None, type=str,
              help='Enable logging by specifying the output logfile')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False),
              help='specify the logging verbosity')
@click.option('--keep/--no-keep', default=False,
              help='Keep the already aquired data, defaults to False')
def acquire_data(output_directory, log, loglevel, keep):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    logger = logging.getLogger('main')
    # get the expected files from the directory
    output_directory = Path(output_directory)
    network_config = output_directory / 'network_config.yaml'
    if not network_config.exists():
        print(f"No network_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    default_config = output_directory / 'default_config.yaml'
    if not default_config.exists():
        print(f"No default_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    init_config = output_directory / 'initial_state_config.yaml'
    if not init_config.exists():
        print(f"No initial_state_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    run_config_files = list(glob.glob(
        str(output_directory.absolute()) + '/' + 'run_*_config.yaml'))
    sorted(run_config_files,
           key=lambda x: int(os.path.basename(x).split('_')[1]))
    run_indices = list(map(lambda x: os.path.basename(x).split('_')[1],
                           run_config_files))

    # read in the configurations
    logger.info('Reading in configurations')
    with open(network_config, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    with open(default_config, 'r') as dcf:
        default_config = yaml.safe_load(dcf.read())
    with open(init_config, 'r') as icf:
        init_config = yaml.safe_load(icf.read())
    run_configs = []
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn()) as progress:
        read_configurations = progress.add_task(
                "[cyan] Read run configurations from disk",
                total=len(run_indices))
        for rcfp in run_config_files:
            with open(rcfp, 'r') as rcf:
                run_configs.append(yaml.safe_load(rcf.read()))
            progress.update(read_configurations, advance=1)
        # instantiate client and server
        # initialize the daq system
        acquire_data_progbar = progress.add_task(
                "[blue]Acquiring Data from the Hexacontroller",
                total=len(run_indices),
                start=False
                )
        daq_system = DAQCoordClient(network_config)
        daq_system.initialize(init_config)
        # setup data taking context for the client

        # delete the old raw files
        if not keep:
            old_raw_files = glob.glob(
                    str(output_directory.absolute())+'/*.raw')
            if len(old_raw_files):
                print('Deleting old Data')
            for file in old_raw_files:
                os.remove(file)

        # take the data
        progress.start_task(acquire_data_progbar)
        for index, run in zip(run_indices, run_configs):
            output_file = output_directory / f'run_{index}_data.raw'
            if not keep or (keep and not output_file.exists()):
                data = daq_system.measure(run)
                with open(output_file, 'wb+') as df:
                    df.write(data)
            progress.update(acquire_data_progbar, advance=1)


def pipelined_acquire_data(configurations: queue.Queue,
                           data_acquisition_progress: queue.Queue,
                           acquired_data: queue.Queue,
                           config_generation_done: threading.Event,
                           daq_initialized: threading.Event,
                           data_acquisition_done: threading.Event,
                           network_configuration: dict,
                           initial_config: dict,
                           output_dir: Path,
                           run_count: int,
                           keep: bool):
    # info needed for the generation of the filenames
    num_digits = math.ceil(math.log(run_count, 10))
    logger = logging.getLogger('data-acquisitor')
    logger.info('Initializing DAQ system')
    daq_system = DAQCoordClient(network_configuration)
    daq_system.initialize(initial_config)
    daq_initialized.set()
    i = 0
    while not config_generation_done.is_set() or not configurations.empty():
        run_config, full_run_config_path = configurations.get()
        raw_file_name = \
            'run_{0:0>{width}}_data.raw'.format(i, width=num_digits)
        raw_file_path = output_dir / raw_file_name
        root_file_name = \
            'run_{0:0>{width}}_data.root'.format(i, width=num_digits)
        hdf_file_name = \
            'run_{0:0>{width}}_data.h5'.format(i, width=num_digits)
        logger.info(f'acquiring data for run {i}')
        if not keep or (keep and not raw_file_path.exists()):
            logger.info(f'gathering Data for run {i}')
            data = daq_system.measure(run_config)
            with open(output_dir / raw_file_name, 'wb+') as rdf:
                rdf.write(data)
        else:
            logger.info('found existing data for run {i},'
                        'skipping acquisition')
        logger.info(f'data acquisition for run {i} done')
        data_acquisition_progress.put(i)
        acquired_data.put(
            (
                raw_file_path,
                output_dir / root_file_name,
                output_dir / hdf_file_name,
                full_run_config_path,
                )
        )
        i += 1
    data_acquisition_done.set()


@click.command()
@click.argument('output_directory', type=click.Path(dir_okay=True),
                metavar='[OUTPUT DIR]')
@click.option('--log', default='daq.log', type=str,
              help='Enable logging by specifying the output logfile')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False),
              help='specify the logging verbosity')
@click.option('--keep/--no-keep', default=False,
              help='Keep the already aquired data, defaults to False')
def pipelined_main(output_directory, log, loglevel, keep):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    logger = logging.getLogger('main')
    # get the expected files from the directory
    output_directory = Path(output_directory)
    network_config = output_directory / 'network_config.yaml'
    if not network_config.exists():
        print(f"No network_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    default_config = output_directory / 'default_config.yaml'
    if not default_config.exists():
        print(f"No default_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    init_config = output_directory / 'initial_state_config.yaml'
    if not init_config.exists():
        print(f"No initial_state_config.yaml found in {output_directory}"
              "exiting ...")
        exit(1)
    run_config_files = list(glob.glob(
        str(output_directory.absolute()) + '/' + 'run_*_config.yaml'))
    sorted(run_config_files,
           key=lambda x: int(os.path.basename(x).split('_')[1]))
    run_config_files = [output_directory / Path(rcf)
                        for rcf in run_config_files]
    run_indices = list(map(lambda x: os.path.basename(x).split('_')[1],
                           run_config_files))
    full_run_config_files = [rcf.parent / (rcf.stem + '_full.yaml')
                             for rcf in run_config_files]

    # read in the configurations
    logger.info('Reading in configurations')
    with open(network_config, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    with open(default_config, 'r') as dcf:
        default_config = yaml.safe_load(dcf.read())
    with open(init_config, 'r') as icf:
        init_config = yaml.safe_load(icf.read())
    # set up the different events that we are looking for
    all_run_configs_generated = threading.Event()
    daq_system_initialized = threading.Event()
    daq_done = threading.Event()

    # set up the queues to pass the data around
    run_configuration_queue = queue.Queue()
    daq_progress_queue = queue.Queue()
    acquired_data_queue = queue.Queue()
    daq_thread = threading.Thread(
            target=pipelined_acquire_data,
            args=(run_configuration_queue,
                  daq_progress_queue,
                  acquired_data_queue,
                  all_run_configs_generated,
                  daq_system_initialized,
                  daq_done,
                  network_config,
                  init_config,
                  output_directory,
                  len(run_indices),
                  keep,
                  )
            )
    daq_thread.start()
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn()) as progress:
        read_configurations = progress.add_task(
                "[cyan] Read run configurations from disk",
                total=len(run_indices))
        daq_progbar = progress.add_task(
                "[turquoise]Acquiring Data from the Test System",
                total=len(run_indices),
                start=False
                )
        for rcfp, frcfp in zip(run_config_files, full_run_config_files):
            if daq_system_initialized.is_set():
                progress.start_task(daq_progbar)
            with open(rcfp, 'r') as rcf:
                run_configuration_queue.put(
                        (yaml.safe_load(rcf.read()), frcfp)
                )
            progress.update(read_configurations, advance=1)
        all_run_configs_generated.set()
        if not daq_system_initialized.is_set():
            daq_system_initialized.wait()
            progress.start_task(daq_progbar)
        while not daq_done.is_set():
            try:
                daq_tasks_completed = daq_progress_queue.get(block=False)
                progress.update(daq_progbar, advance=daq_tasks_completed)
            except queue.Empty:
                pass
            try:
                _ = acquired_data_queue.get(block=False)
            except queue.Empty:
                pass
