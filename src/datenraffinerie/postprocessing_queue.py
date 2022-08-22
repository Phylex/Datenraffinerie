import threading
import queue
import logging
import os
import sys
import yaml
from time import sleep
from pathlib import Path
import glob
import click
from . import dict_utils as dctu
from . import analysis_utilities as anu


def unpack_data(raw_data_queue: queue.Queue,
                frack_data_queue: queue.Queue,
                stop_event: threading.Event,
                max_parallel_unpackers: int,
                logger: logging.Logger,
                raw_data: bool):
    running_tasks = []
    while not stop_event.is_set() or not raw_data_queue.empty() \
            or not len(running_tasks) == 0:
        if len(running_tasks) < max_parallel_unpackers:
            try:
                raw_path, unpack_path, fracked_path, full_config_path = \
                        raw_data_queue.get(block=False)
                logger.info('Received data to unpack,'
                            f'{os.path.basename(raw_path)}')
                running_tasks.append((
                        anu.start_unpack(
                            raw_path,
                            unpack_path,
                            logging.getLogger(
                                f'unpack-{os.path.basename(raw_path)}'),
                            raw_data=raw_data
                            ),
                        raw_path,
                        unpack_path,
                        fracked_path,
                        full_config_path
                        )
                )
            except queue.Empty:
                pass
        del_indices = []
        for i, (task, raw_path, unpack_path, fracked_path, full_config_path) \
                in enumerate(running_tasks):
            returncode = task.poll()
            if returncode is None:
                continue
            del_indices.append(i)
            if returncode == 0:
                logger.info('created root file from '
                            f'{os.path.basename(raw_path)}')
                logger.info('putting fracker task on the queue')
                frack_data_queue.put(
                        (raw_path, unpack_path, fracked_path, full_config_path)
                )
            if returncode > 0:
                logger.error(f'failed to created root file from {raw_path}, '
                             f'unpacker returned error code {returncode}')
                os.remove(raw_path)
            if returncode < 0:
                logger.error(f'failed to created root file from {raw_path}, '
                             'unpacker got terminated')
                os.remove(raw_path)
            raw_data_queue.task_done()
        running_tasks = list(filter(lambda x: running_tasks.index(x)
                                    not in del_indices, running_tasks))


def frack_data(frack_data_queue: queue.Queue,
               stop_event: threading.Event,
               max_parallel_frackers: int,
               logger: logging.Logger,
               raw_data: bool,
               keep_root: bool,
               compression: int,
               columns: list):
    running_tasks = []
    while not stop_event.is_set() or not frack_data_queue.empty() \
            or not len(running_tasks) == 0:
        if len(running_tasks) < max_parallel_frackers:
            try:
                raw_path, unpack_path, fracked_path, full_config_path = \
                        frack_data_queue.get(block=False)
                logger.info('Received data to frack, '
                            f'{os.path.basename(unpack_path)}')
                running_tasks.append((
                        anu.start_compiled_fracker(
                            unpack_path,
                            fracked_path,
                            full_config_path,
                            raw_data,
                            columns,
                            compression,
                            logger),
                        raw_path,
                        unpack_path,
                        fracked_path,
                        full_config_path
                        )
                )
            except queue.Empty:
                pass
        del_indices = []
        for i, (task, raw_path, unpack_path, fracked_path, full_config_path) \
                in enumerate(running_tasks):
            returncode = task.poll()
            if returncode is None:
                continue
            del_indices.append(i)
            if returncode == 0:
                logger.info(
                    f'created hdf file from {os.path.basename(unpack_path)}')

            if returncode > 0:
                logger.error(
                    'failed to created root file from '
                    f'{os.path.basename(unpack_path)}, '
                    f'unpacker returned error code {returncode}')
                os.remove(raw_path)
            if returncode < 0:
                logger.error('failed to created hdf file from '
                             f'{os.path.basename(raw_path)}, '
                             'unpacker got terminated')
                os.remove(raw_path)
            if not keep_root:
                os.remove(unpack_path)
            os.remove(full_config_path)
            frack_data_queue.task_done()
        running_tasks = list(filter(lambda x: running_tasks.index(x)
                                    not in del_indices, running_tasks))


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
@click.option('--unpack_tasks', default=1, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--fracker_tasks', default=3, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--compression', '-c', default=3, type=int,
              help='Set the compression for the hdf file, 0 = no compression'
                   ' 9 = best compression')
def main(output_dir, log, loglevel, root, unpack_tasks,
         fracker_tasks, compression):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    # read in the information for the postprocessing from the config files
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
        raw_data = True if mode == 'full' else False

    # prepare the threading environment
    unpack_queue = queue.Queue()
    frack_queue = queue.Queue()
    stop_threads = threading.Event()
    unpack_thread = threading.Thread(
            target=unpack_data,
            args=(unpack_queue,
                  frack_queue,
                  stop_threads,
                  max(1, unpack_tasks),
                  logging.getLogger('unpack-coordinator'),
                  raw_data
                  )
            )
    frack_thread = threading.Thread(
            target=frack_data,
            args=(frack_queue,
                  stop_threads,
                  max(1, fracker_tasks),
                  logging.getLogger('fracking-coordinator'),
                  raw_data,
                  root,
                  compression,
                  data_columns
                  )
            )
    unpack_thread.start()
    frack_thread.start()

    # read in the data and start the postprocessing
    run_config_paths = glob.glob(
            str(output_dir.absolute()) + '/run_*_config.yaml')
    run_raw_data_paths = glob.glob(
            str(output_dir.absolute()) + '/run_*_data.raw')
    full_run_config_dir = os.path.dirname(run_config_paths[0])
    run_config_paths = sorted(
            run_config_paths, key=lambda x: int(x.split('_')[-2]))
    run_raw_data_paths = sorted(
            run_raw_data_paths, key=lambda x: int(x.split('_')[-2]))
    run_root_data_paths = list(
            map(lambda x: os.path.splitext(x)[0] + '.root',
                run_raw_data_paths))
    run_hdf_data_paths = list(
            map(lambda x: os.path.splitext(x)[0] + '.h5',
                run_raw_data_paths))
    if procedure['diff']:
        initial_config_file = output_dir / 'initial_state_config.yaml'
        with open(initial_config_file, 'r') as icf:
            initial_config = yaml.safe_load(icf.read())
        default_config_file = output_dir / 'default_config.yaml'
        with open(default_config_file, 'r') as dfc:
            default_config = yaml.safe_load(dfc.read())
        full_config = dctu.update_dict(default_config, initial_config)
        for run_config_path, raw_data_path, root_data_path, hdf_data_path in \
                zip(run_config_paths, run_raw_data_paths,
                    run_root_data_paths, run_hdf_data_paths):
            with open(run_config_path, 'r') as rcfgf:
                run_config_patch = yaml.safe_load(rcfgf.read())
            dctu.update_dict(full_config, run_config_patch, in_place=True)
            full_run_config_path = full_run_config_dir + '/' + \
                os.path.splitext(os.path.basename(run_config_path))[0] + \
                '_full.yaml'
            with open(full_run_config_path, 'w+') as frcf:
                frcf.write(yaml.dump(full_config))
            unpack_queue.put(
                    (Path(raw_data_path),
                     Path(root_data_path),
                     Path(hdf_data_path),
                     Path(full_run_config_path)))
    else:
        for run_config_path, raw_data_path, root_data_path, hdf_data_path in \
                zip(run_config_paths, run_raw_data_paths,
                    run_root_data_paths, run_hdf_data_paths):
            unpack_queue.put(
                    (Path(raw_data_path),
                     Path(root_data_path),
                     Path(hdf_data_path),
                     Path(run_config_path)))
    stop_threads.set()
    unpack_thread.join()
    frack_thread.join()
