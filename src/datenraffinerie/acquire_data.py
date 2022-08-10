from .daq_coordination import DAQCoordClient
import yaml
import glob
import click
from pathlib import Path
import logging
import os
from progress.bar import Bar

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
    bar = Bar('reading run configurations from disk', max=len(run_indices))
    for rcfp in run_config_files:
        with open(rcfp, 'r') as rcf:
            run_configs.append(yaml.safe_load(rcf.read()))
        bar.next()
    bar.finish()
    # instantiate client and server
    # initialize the daq system
    print('Initializing DAQ-System')
    daq_system = DAQCoordClient(network_config)
    daq_system.initialize(init_config)
    # setup data taking context for the client

    # delete the old raw files
    if not keep:
        old_raw_files = glob.glob(str(output_directory.absolute())+'/*.raw')
        if len(old_raw_files):
            print('Deleting old Data')
        for file in old_raw_files:
            os.remove(file)

    # take the data
    bar = Bar('Acquiring Data', max=len(run_indices))
    for index, run in zip(run_indices, run_configs):
        output_file = output_directory / f'run_{index}_data.raw'
        if not keep or (keep and not output_file.exists()):
            data = daq_system.measure(run)
            with open(output_file, 'wb+') as df:
                df.write(data)
        bar.next()
    bar.finish()


if __name__ == "__main__":
    acquire_data()
