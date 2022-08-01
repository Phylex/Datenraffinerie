from .import control_adapter as ctrla
from . import dict_utils as dtu
from .zmq_i2c_client import ROC_configuration_client as sc_client
import yaml
import glob
import click
from pathlib import Path
import logging
import os


@click.command()
@click.argument('config_directory', type=click.Path(dir_okay=True),
                metavar='[directory containing the run configurations]')
@click.option('--diff', default=False, type=bool)
@click.option('--log', default=None, type=str)
@click.option('--loglevel', default='INFO')
def acquire_data(config_directory, diff, log):
    if log is not None:
        logging.basicConfig(log, )
    
    # get the expected files from the directory
    config_directory = Path(config_directory)
    network_config = config_directory / 'network_config.yaml'
    if not network_config.exists():
        print(f"No network_config.yaml found in {config_directory}"
              "exiting ...")
        exit(1)
    default_config = config_directory / 'default_config.yaml'
    if not default_config.exists():
        print(f"No default_config.yaml found in {config_directory}"
              "exiting ...")
        exit(1)
    init_config = config_directory / 'initial_state_config.yaml'
    if not init_config.exists():
        print(f"No initial_state_config.yaml found in {config_directory}"
              "exiting ...")
        exit(1)
    run_configs = list(Path(glob.glob(
        str(config_directory.absolute()) + '/' + 'config_run_*.yaml')))
    sorted(run_configs,
           key=lambda x: int(os.path.basename(x).split('_')[-1].split('.')[0]))
    print(f'Found configurations for {len(run_configs)} runs')

    # read in the configurations
    with open(network_config, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    with open(default_config, 'r') as dcf:
        default_config = yaml.safe_load(dcf.read())
    with open(init_config, 'r') as icf:
        init_config = yaml.safe_load(icf.read())
    run_configs = []
    for rcfp in run_configs:
        with open(rcfp, 'r') as rcf:
            run_configs.append(yaml.safe_load(rcf.read()))
    server_net_config = network_config['server']
    client_net_config = network_config['client']
    target_net_config = network_config['target']
    daq_system = ctrla.DAQSystem(
            server_hostname=server_net_config['hostname'],
            server_port=server_net_config['port'],
            client_hostname=client_net_config['hostname'],
            client_port=client_net_config['port'])
    # TODO instantiate the client
    target = sc_client(target_net_config['hostname'])
    daq_system.initalize(dtu.diff_dict(default_config, init_config))
    daq_system.setup_data_taking_context()
    for i, run in enumerate(run_configs):
        target.set(run, readback=True)
        daq_system.configure(run['target'])
        daq_system.take_data(f'run_data_{i}.raw')


if __name__ == "__main__":
    acquire_data()
