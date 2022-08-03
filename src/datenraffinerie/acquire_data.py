from .import control_adapter as ctrla
from hgcroc_configuration_client.client import Client as sc_client
import yaml
import glob
import click
from pathlib import Path
import logging
import os

log_level_dict = {'DEBUG': logging.DEBUG,
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
        logging.basicConfig(filename=log, level=log_level_dict[loglevel],
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
    print(f'Found configurations for {len(run_config_files)} runs')

    # read in the configurations
    with open(network_config, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    server_net_config = network_config['server']
    client_net_config = network_config['client']
    target_net_config = network_config['target']
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
    target = sc_client(target_net_config['hostname'])
    daq_system = ctrla.DAQSystem(
        server_hostname=server_net_config['hostname'],
        server_port=server_net_config['port'],
        client_hostname=client_net_config['hostname'],
        client_port=client_net_config['port'])
    # initialize the daq system
    daq_system.initalize(init_config)
    # setup data taking context for the client
    daq_system.setup_data_taking_context()
    print('Initialized DAQ-System')
    # initialize the target
    try:
        initial_target_config = init_config['target']
    except KeyError:
        initial_target_config = {}
    target.set(initial_target_config, readback=True)
    # take the data
    for i, run in enumerate(run_configs):
        logging.info(f'Gathering Data for run {i}')
        print(f'Gathering Data for run {i}')
        try:
            logging.debug(f'run config:\n{yaml.dump(run)}')
            target_run_config = run['target']
        except KeyError:
            target_run_config = {}
        if target_run_config != {}:
            logging.debug(
                f'loading run config to target\n{yaml.dump(target_run_config)}'
            )
            target.set(target_run_config, readback=True)
        daq_system.configure(run)
        daq_system.take_data(output_directory / f'run_data_{i}.raw')


if __name__ == "__main__":
    acquire_data()
