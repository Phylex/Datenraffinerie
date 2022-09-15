import threading
import queue
import logging
import os
import sys
import yaml
from pathlib import Path
import glob
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import MofNCompleteColumn
from rich.progress import TextColumn
from rich.progress import BarColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn
import click
from . import analysis_utilities as anu
from time import sleep


def unpack_data(raw_data_queue: queue.Queue,
                unpack_reporting_queue: queue.Queue,
                root_data_queue: queue.Queue,
                data_taking_done: threading.Event,
                unpacking_done: threading.Event,
                max_parallel_unpackers: int,
                raw_data: bool,
                characterisation_mode: bool):
    logger = logging.getLogger('unpack-data-thread')
    running_tasks = []
    while not data_taking_done.is_set() or not raw_data_queue.empty() \
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
                            raw_data=raw_data,
                            characMode=characterisation_mode
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
            logger.debug(f'currently running tasks {running_tasks}')
            unpack_reporting_queue.put(1)
            del_indices.append(i)
            if returncode == 0:
                logger.info('created root file from '
                            f'{os.path.basename(raw_path)}')
                logger.info('putting fracker task on the queue')
                root_data_queue.put(
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
        sleep(.05)
    unpacking_done.set()


def frack_data(frack_data_queue: queue.Queue,
               frack_report_queue: queue.Queue,
               previous_task_complete: threading.Event,
               fracking_done: threading.Event,
               max_parallel_frackers: int,
               raw_data: bool,
               keep_root: bool,
               compression: int,
               columns: list):
    running_tasks = []
    logger = logging.getLogger('data-fracking-thread')
    while not previous_task_complete.is_set() or not frack_data_queue.empty() \
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
            logger.debug(f'currently running tasks {running_tasks}')
            frack_report_queue.put(1)
            del_indices.append(i)
            if returncode == 0:
                logger.info(
                    f'created {os.path.basename(fracked_path)}')

            if returncode > 0:
                logger.error(
                    'failed to created hdf file from '
                    f'{os.path.basename(unpack_path)}, '
                    f'fracker returned error code {returncode}')
                os.remove(raw_path)
            if returncode < 0:
                logger.error('failed to created hdf file from '
                             f'{os.path.basename(raw_path)}, '
                             'unpacker got terminated')
                os.remove(raw_path)
            if not keep_root:
                os.remove(unpack_path)
            frack_data_queue.task_done()
        running_tasks = list(filter(lambda x: running_tasks.index(x)
                                    not in del_indices, running_tasks))
        sleep(.05)
    fracking_done.set()


def synchronize_with_config_generation(
        unpack_out_queue: queue.Queue,
        synced_with_config_generation: queue.Queue,
        generated_full_configurations: list,
        previous_task_complete: threading.Event,
        current_task_complete: threading.Event):
    tasks_waiting_for_config = []
    while not previous_task_complete.is_set() \
            and not unpack_out_queue.empty() \
            and not len(tasks_waiting_for_config) == 0:
        try:
            task = unpack_out_queue.get(block=False)
            raw_path, unpack_path, fracked_path, full_config_path = task
            if full_config_path in generated_full_configurations:
                synced_with_config_generation.put(task)
            else:
                tasks_waiting_for_config.append(task)
        except queue.Empty:
            pass
        del_indices = []
        for i, task in enumerate(tasks_waiting_for_config):
            raw_path, unpack_path, fracked_path, full_config_path = task
            if full_config_path in generated_full_configurations:
                synced_with_config_generation.put(task)
                del_indices.append(i)
            else:
                tasks_waiting_for_config.append(task)
        tasks_waiting_for_config = list(
                filter(lambda x: tasks_waiting_for_config.index(x)
                       not in del_indices, tasks_waiting_for_config))


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location containing the config and data]')
@click.option('--log', type=str, default='post.log',
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
@click.option('--root/--no-root', default=False,
              help='keep the rootfile generated as intermediary')
@click.option('--unpack_tasks', default=1, type=int,
              help='number of unpacking tastks to run in parallel')
@click.option('--frack_tasks', default=3, type=int,
              help='number of frackers to run in parallel')
@click.option('--compression', '-c', default=3, type=int,
              help='Set the compression for the hdf file, 0 = no compression'
                   ' 9 = best compression')
def main(output_dir, log, loglevel, root, unpack_tasks,
         frack_tasks, compression):
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
        try:
            data_format = procedure['data_format']
        except KeyError:
            data_format = 'raw'
        characterisation_mode = True \
            if data_format == 'characterisation' else False

    # prepare the threading environment
    raw_data_queue = queue.Queue()
    root_data_queue = queue.Queue()
    unpack_reporting_queue = queue.Queue()
    fracker_reporting_queue = queue.Queue()
    data_taking_done = threading.Event()
    unpack_done = threading.Event()
    fracking_done = threading.Event()

    # initilize the threads
    unpack_thread = threading.Thread(
            target=unpack_data,
            args=(raw_data_queue,
                  unpack_reporting_queue,
                  root_data_queue,
                  data_taking_done,
                  unpack_done,
                  max(1, unpack_tasks),
                  raw_data,
                  characterisation_mode
                  )
            )
    frack_thread = threading.Thread(
            target=frack_data,
            args=(root_data_queue,
                  fracker_reporting_queue,
                  unpack_done,
                  fracking_done,
                  max(1, frack_tasks),
                  raw_data,
                  root,
                  compression,
                  data_columns,
                  )
            )

    unpack_thread.start()
    frack_thread.start()

    # read in the data and start the postprocessing
    run_config_paths = glob.glob(
            str(output_dir.absolute()) + '/run_*_config.yaml')
    run_raw_data_paths = glob.glob(
            str(output_dir.absolute()) + '/run_*_data.raw')
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
    full_config_paths = list(
            map(lambda x: Path(os.path.splitext(x)[0] + '_full.yaml'),
                run_config_paths))
    run_count = len(run_config_paths)
    for full_config_path, raw_data_path, root_data_path, hdf_data_path in \
            zip(full_config_paths, run_raw_data_paths,
                run_root_data_paths, run_hdf_data_paths):
        if not full_config_path.exists():
            print(f"Full config file {full_config_path} not found")
            data_taking_done.set()
            unpack_done.set()
            unpack_thread.join()
            frack_thread.join()
            sys.exit(1)
        raw_data_queue.put(
                (Path(raw_data_path),
                 Path(root_data_path),
                 Path(hdf_data_path),
                 Path(full_config_path)))
    data_taking_done.set()
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn()) as progress:
        unpack_progress_bar = progress.add_task(
                'Unpacking data',
                total=run_count)
        frack_progress_bar = progress.add_task(
                'fracking data',
                total=run_count)
        while not fracking_done.is_set():
            try:
                _ = unpack_reporting_queue.get(block=False)
                progress.update(unpack_progress_bar, advance=1)
            except queue.Empty:
                pass
            try:
                _ = fracker_reporting_queue.get(block=False)
                progress.update(frack_progress_bar, advance=1)
            except queue.Empty:
                pass
            sleep(0.05)
        unpack_thread.join()
        frack_thread.join()
