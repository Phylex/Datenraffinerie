import sys
import multiprocessing
import click
from .valve_yard import ValveYard
from .config_utilities import ConfigFormatError, parse_config_file
from .control_adapter import DAQConfigError
from .daq_coordination import coordinate_daq_access
import .config_utilities as cfu
import logging
import luigi
import yaml


@click.command()
@click.argument('netcfg', type=click.File('r'))
@click.argument('config', type=click.Path(exists=True))
@click.argument('procedure', type=str)
@click.argument('output', type=click.Path())
@click.option('-a', '--analysis_path', 'analysis_path', type=click.Path(exists=True))
@click.option('-w', '--workers', 'workers', type=int, default=1)
def cli(netcfg, config, procedure, workers, output, analysis_path):
    """ The command line interface to the datenraffinerie intended to
    be one of the primary interfaces for the users.
    """
    try:
        netcfg = yaml.safe_load(netcfg.read())
    except yaml.YAMLError as err:
        print('Error reading in the network config:\n'
              + str(err) + '\nexiting ..')
        sys.exit(1)
    p = multiprocessing.Process(target=coordinate_daq_access, args=netcfg)
    try:
        run_result = luigi.build([ValveYard(
            click.format_filename(config),
            procedure,
            output,
            analysis_path,
            netcfg)],
            local_scheduler=True,
            workers=workers,
        )
        print(run_result)
    except ConfigFormatError as err:
        print(err.message)
        sys.exit(1)
    except DAQConfigError as err:
        print("The Configuration of one of the executed"
              " DAQ procedures is malformed: ")
        print(err.message)
        sys.exit(1)
    except Exception as err:
        print("An error occured that was not properly caught")
        print(err)
        sys.exit(1)
