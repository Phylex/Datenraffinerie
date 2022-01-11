import sys
import click
from .valve_yard import ValveYard
from .config_utilities import ConfigFormatError
from .control_adapter import DAQConfigError
import logging
import luigi


@click.command()
@click.argument('config', type=click.Path(exists=True))
@click.argument('procedure', type=str)
@click.argument('output', type=click.Path())
@click.option('-w', '--workers', 'workers', type=int, default=4)
def cli(config, procedure, workers, output):
    try:
        run_result = luigi.build([ValveYard(
            click.format_filename(config),
            procedure,
            output)],
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
