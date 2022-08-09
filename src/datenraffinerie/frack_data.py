from . import analysis_utilities as anu
from uproot.exceptions import KeyInFileError
from . import dict_utils as dcu
import os
import shutil
import logging
from pathlib import Path
import yaml
import click
import sys


def frack_data(raw_data_file_path, full_run_config, mode,
               columns, keep_root: bool):
    logger = logging.getLogger(f'fracker-{raw_data_file_path}')
    # generate the paths for the output files
    unpacked_file_path = os.path.splitext(raw_data_file_path)[0] + '.root'
    formatted_data_path = os.path.splitext(raw_data_file_path)[0] + '.h5'

    # generate the intermediary root file
    result = anu.unpack_raw_data_into_root(
            raw_data_file_path,
            unpacked_file_path,
    )

    # if the unpaack command failed remove the raw file to
    # trigger the Datafield to rerun the data taking
    if result != 0 and unpacked_file_path.exists():
        logger.error('unpack falied, removing raw data')
        os.remove(unpacked_file_path)
        os.remove(raw_data_file_path)
        return
    if not unpacked_file_path.exists():
        logger.error('unpack falied, removing raw data')
        os.remove(raw_data_file_path)
        return

    # if the fracker can be found run it
    logger.info('Converting Root file to HDF5')
    if shutil.which('fracker') is not None:
        logger.debug('fracker cmd-tool found')
        retval = anu.run_compiled_fracker(
                str(unpacked_file_path.absolute()),
                str(formatted_data_path.absolute()),
                full_run_config,
                mode,
                columns)
        if retval != 0:
            logger.error("The fracker failed")
            if formatted_data_path.exists():
                logger.error("removing hdf file, keeping ")
                os.remove(formatted_data_path)
    # otherwise fall back to the python code
    else:
        logger.debug('fracker cmd not found, running python code')
        try:
            anu.reformat_data(unpacked_file_path,
                              formatted_data_path,
                              full_run_config,
                              mode,
                              columns)
        except KeyInFileError:
            os.remove(unpacked_file_path)
            os.remove(raw_data_file_path)
        except FileNotFoundError:
            logger.error('Python reformatting code failed')
            return
    if not keep_root:
        os.remove(unpacked_file_path)


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location to write the configuration files to]')
@click.option('--log', type=str, default=None,
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
def main(output_dir, log, loglevel):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    output_dir = Path(output_dir)
    with open(output_dir / 'procedure_config.yaml') as pcf:
        procedure = yaml.safe_load(pcf.read())
        try:
            data_columns = procedure['data_columns']
        except KeyError:
            print('The procedure needs to specify data columns')
            sys.exit(1)
    default_config_file = output_dir / 'default_config.yaml'
    with open(default_config_file, 'r') as dfc:
        default_config = yaml.safe_load(dfc.read())
    initial_config_file = output_dir / 'initial_state_config.yaml'
    with open(initial_config_file, 'r') as icf:
        initial_config = yaml.safe_load(icf.read())
    full_initial_config = dcu.update_dict(default_config, initial_config)

