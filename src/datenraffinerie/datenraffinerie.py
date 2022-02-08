import sys
import multiprocessing
import click
import luigi
import yaml
from .valve_yard import ValveYard
from .config_utilities import ConfigFormatError
from .control_adapter import DAQConfigError
from .daq_coordination import coordinate_daq_access


@click.command()
@click.argument('netcfg', type=click.File('r'),
                metavar='[network configuration file]')
@click.argument('config', type=click.Path(exists=True),
                metavar='[main configuration file]')
@click.argument('procedure', type=str,
                metavar='[Procedure to be run by the datenraffinerie]')
@click.argument('output', type=click.Path(),
                metavar='[data output directory]')
@click.option('-a', '--analysis_path', 'analysis_path', type=click.Path(exists=True),
              help='specify the path to the python module containing the analyses')
@click.option('-w', '--workers', 'workers', type=int, default=1,
              help='specify the amount of parallel tasks to be executed')
@click.option('-l', '--loop', 'loop', is_flag=True, default=False,
              help='tell the scan to run the measurements in a loop'
                   + ' instead of creating them in separate tasks')
def cli(netcfg, config, procedure, workers, output, analysis_path, loop):
    """ The command line interface to the datenraffinerie intended to
    be one of the primary interfaces for the users.
    """
    try:
        netcfg = yaml.safe_load(netcfg.read())
    except yaml.YAMLError as err:
        print('Error reading in the network config:\n'
              + str(err) + '\nexiting ..')
        sys.exit(1)
    daq_coordination_process = multiprocessing.Process(target=coordinate_daq_access, args=(netcfg, ))
    daq_coordination_process.start()
    try:
        run_result = luigi.build([ValveYard(
            click.format_filename(config),
            procedure,
            output,
            analysis_path,
            netcfg,
            loop='true' if loop else 'false')],
            local_scheduler=True,
            workers=workers,
        )
        print(run_result)
    except ConfigFormatError as err:
        print(err.message)
    except DAQConfigError as err:
        print("The Configuration of one of the executed"
              " DAQ procedures is malformed: ")
        print(err.message)
    except Exception as err:
        print("An error occured that was not properly caught")
        print(err)
    finally:
        daq_coordination_process.kill()
        daq_coordination_process.join()
        sys.exit(1)
