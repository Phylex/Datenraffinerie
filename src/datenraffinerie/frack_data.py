from . import analysis_utilities as anu
from . import dict_utils as dcu
from progress.bar import Bar
from time import sleep
import glob
import os
import logging
from pathlib import Path
import yaml
import click
import sys


def unpack_in_parallel(waiting_tasks, parallel_tasks,
                       logger, bar: bool, mode: str):
    running_tasks = []
    failed_tasks = []
    successful_tasks = []
    if bar:
        prog_bar = Bar('creating intermediary root files'.ljust(50, ' '),
                       max=len(waiting_tasks))
    while len(waiting_tasks) > 0 or len(running_tasks) > 0:
        # check whether there another task can be run
        while parallel_tasks > len(running_tasks):
            try:
                (raw_path, unpacked_path, formatted_path, full_config_path) = \
                        waiting_tasks.pop()
            except IndexError:
                break
            if mode == 'full':
                raw_data = True
            else:
                raw_data = False
            running_tasks.append((
                anu.start_unpack(raw_path,
                                 unpacked_path,
                                 logging.getLogger(f'unpack-{raw_path}'),
                                 raw_data=raw_data),
                raw_path,
                unpacked_path,
                formatted_path,
                full_config_path
                )
            )
        del_indices = []
        for i, (task, raw_path, unpacked_path,
                formatted_path, full_config_path) \
                in enumerate(running_tasks):
            returncode = task.poll()
            if returncode is None:
                continue
            del_indices.append(i)
            if returncode == 0:
                logger.info(f'created root file from {raw_path}')
                successful_tasks.append(
                        (unpacked_path, formatted_path, full_config_path)
                )
            if returncode > 0:
                logger.error(f'failed to created root file from {raw_path}, '
                             f'unpacker returned error code {returncode}')
                failed_tasks.append((raw_path, unpacked_path))
            if returncode < 0:
                logger.error(f'failed to created root file from {raw_path}, '
                             'unpacker got terminated')
                failed_tasks.append((raw_path, unpacked_path))
            if bar:
                prog_bar.next()
        del_indices = sorted(del_indices, reverse=True)
        for i in del_indices:
            del running_tasks[i]
        sleep(.2)
    if bar:
        prog_bar.finish()
    return successful_tasks, failed_tasks


def frack_in_parallel(waiting_tasks, parallel_tasks,
                      logger, bar, mode: str, columns,
                      compression):
    running_tasks = []
    failed_tasks = []
    successful_tasks = []
    if bar:
        prog_bar = Bar('creating hdf files'.ljust(50, ' '),
                       max=len(waiting_tasks))
    while len(waiting_tasks) > 0 or len(running_tasks) > 0:
        # check whether there another task can be run
        while parallel_tasks > len(running_tasks):
            try:
                (unpacked_path, formatted_path, full_config_path) = \
                        waiting_tasks.pop()
            except IndexError:
                break
            if mode == 'full':
                raw_data = True
            else:
                raw_data = False
            running_tasks.append((
                anu.start_compiled_fracker(unpacked_path, formatted_path,
                                           full_config_path, raw_data,
                                           columns, compression, logger),
                unpacked_path,
                formatted_path,
                full_config_path
                )
            )
        del_indices = []
        for i, (task, unpacked_path, formatted_path, full_config_path) \
                in enumerate(running_tasks):
            returncode = task.poll()
            if returncode is None:
                continue
            del_indices.append(i)
            if returncode == 0:
                logger.info(
                        f'created {formatted_path} file from {unpacked_path}')
                successful_tasks.append((unpacked_path, formatted_path))
            if returncode > 0:
                logger.error(
                        f'failed to created hdf file from {formatted_path}, '
                        f'fracker returned error code {returncode}')
                failed_tasks.append((unpacked_path, formatted_path))
            if returncode < 0:
                logger.error(
                        f'failed to created hdf file from {formatted_path}, '
                        'fracker got terminated')
                failed_tasks.append((unpacked_path, formatted_path))
            if bar:
                prog_bar.next()
        del_indices = sorted(del_indices, reverse=True)
        for i in del_indices:
            del running_tasks[i]
        sleep(.2)
    if bar:
        prog_bar.finish()
    return successful_tasks, failed_tasks


def frack_data(raw_data_paths, full_run_config_paths, mode, columns,
               parallel_tasks: int = 2,
               bar: bool = False, compression: bool = 3):
    logger = logging.getLogger('fracker')
    # generate the paths for the output files
    unpacked_data_paths = [Path(os.path.splitext(rdfp)[0] + '.root')
                           for rdfp in raw_data_paths]
    formatted_data_paths = [Path(os.path.splitext(rdfp)[0] + '.h5')
                            for rdfp in raw_data_paths]

    # generate the intermediary root files
    logger.info('Converting raw files into root files')
    unpack_tasks = list(
            zip(raw_data_paths, unpacked_data_paths,
                formatted_data_paths, full_run_config_paths)
    )
    unpack_tasks.reverse()
    try:
        successful_tasks, failed_tasks = \
            unpack_in_parallel(unpack_tasks, parallel_tasks, logger, bar, mode)
    except FileNotFoundError as err:
        logger.critical(err.args[0])
        sys.exit(1)
    for (raw_path, unpacked_path) in failed_tasks:
        print(f'The creation of the root file failed for {raw_path}, '
              'removing {raw_path}')
        os.remove(raw_path)
        try:
            os.remove(unpacked_path)
        except FileNotFoundError:
            pass
    fracker_tasks = successful_tasks
    try:
        successful_fracker_tasks, failed_fracker_tasks = \
            frack_in_parallel(fracker_tasks, parallel_tasks,
                              logger, bar, mode, columns, compression)
    except FileNotFoundError as err:
        logger.critical(err.args[0])
        print('Unable to find compiled fracker, exiting ...')
        sys.exit(2)
    for (unpacked_path, formatted_path) in failed_fracker_tasks:
        print(f'The creation of the hdf file failed for {unpacked_path}, '
              'removing {unpacked_path}')
        os.remove(unpacked_path)
        try:
            os.remove(formatted_path)
        except FileNotFoundError:
            pass


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location containing the config and data]')
@click.option('--log', type=str, default=None,
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
@click.option('--root/--no-root', default=False,
              help='keep the rootfile generated as intermediary')
@click.option('--parallel_tasks', default=2, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--compression', '-c', default=3, type=int,
              help='Set the compression for the hdf file, 0 = no compression'
                   ' 9 = best compression')
def main(output_dir, log, loglevel, root, parallel_tasks, compression):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    output_dir = Path(output_dir)
    with open(output_dir / 'postprocessing_config.yaml') as pcf:
        procedure = yaml.safe_load(pcf.read())
        try:
            data_columns = procedure['data_columns']
        except KeyError:
            print('The procedure needs to specify data columns')
            sys.exit(1)
        try:
            mode = procedure['mode']
        except KeyError:
            mode = 'summary'
    default_config_file = output_dir / 'default_config.yaml'
    with open(default_config_file, 'r') as dfc:
        default_config = yaml.safe_load(dfc.read())
    initial_config_file = output_dir / 'initial_state_config.yaml'
    with open(initial_config_file, 'r') as icf:
        initial_config = yaml.safe_load(icf.read())
    full_config = dcu.update_dict(default_config, initial_config)
    run_config_paths = glob.glob(
            str(output_dir.absolute()) + '/run_*_config.yaml')
    run_raw_data_files = glob.glob(
            str(output_dir.absolute()) + '/run_*_data.raw')
    sorted(run_config_paths, key=lambda x: int(x.split('_')[-2]))
    sorted(run_raw_data_files, key=lambda x: int(x.split('_')[-2]))

    # prepare the data so that we can launch the conversions in parallel
    full_run_config_paths = []
    full_run_config_dir = os.path.dirname(run_config_paths[0])
    if procedure['diff']:
        bar = Bar('generating fully qualified configurations'.ljust(50, ' '),
                  max=len(run_config_paths))
        for run_config_file in run_config_paths:
            with open(run_config_file, 'r') as rcfgf:
                run_config_patch = yaml.safe_load(rcfgf.read())
            dcu.update_dict(full_config, run_config_patch, in_place=True)
            full_run_config_path = full_run_config_dir + '/' + \
                os.path.splitext(os.path.basename(run_config_file))[0] + \
                '_full.yaml'
            with open(full_run_config_path, 'w+') as frcf:
                frcf.write(yaml.dump(full_config))
            full_run_config_paths.append(Path(full_run_config_path))
            bar.next()
        bar.finish()
    else:
        full_run_config_paths = run_config_paths

    # actually do the postprocessing
    frack_data(run_raw_data_files,
               full_run_config_paths,
               mode,
               data_columns,
               parallel_tasks,
               bar=True,
               compression=compression
               )
    if not root:
        root_files = glob.glob(str(output_dir.absolute()) + '/*.root')
        for rf in root_files:
            logging.info(f'Deleting unneeded rootfile {rf}')
            os.remove(rf)
    for config_file in full_run_config_paths:
        logging.info(f'Deleting unneeded full_config_file {config_file}')
        os.remove(config_file)
    print('Done')
