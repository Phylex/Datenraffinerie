from .daq_coordination import DAQCoordClient
import yaml
import math
import glob
import click
from pathlib import Path
import logging
import os

_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command()
@click.argument('output_directory', type=click.Path(dir_okay=True),
                metavar='[directory containing the run configurations]')
@click.option('--diff', default=False, type=bool)
@click.option('--log', default=None, type=str)
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
def acquire_data(output_directory, diff, log, loglevel):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
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
    run_indices = list(map(lambda x: os.path.basename(x).split('_')[1]))
    print(f'Found configurations for {len(run_config_files)} runs')

    # read in the configurations
    with open(network_config, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    daq_system = DAQCoordClient(network_config)
    with open(default_config, 'r') as dcf:
        default_config = yaml.safe_load(dcf.read())
    with open(init_config, 'r') as icf:
        init_config = yaml.safe_load(icf.read())
    run_configs = []
    for rcfp in run_config_files:
        with open(rcfp, 'r') as rcf:
            run_configs.append(yaml.safe_load(rcf.read()))
    print('Finished loading configurations')
    # instantiate client and server
    # initialize the daq system
    daq_system.initialize(init_config)
    # setup data taking context for the client
    print('Initialized DAQ-System')
    # take the data
    old_raw_files = glob.glob(output_directory.absolute()+'/*.raw')
    for file in old_raw_files:
        os.remove(file)
    for index, run in zip(run_indices, run_configs):
        data = daq_system.measure(run)
        output_file = output_directory / f'run_{index}_data.raw'
        with open(output_file, 'wb+') as df:
            df.write(data)
        print('Acuired Data for run {int(index)}', end='\r')


if __name__ == "__main__":
    acquire_data()
