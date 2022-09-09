import click
import os
import glob
import shutil
import yaml
import math
import logging
import queue
import threading
from pathlib import Path
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import MofNCompleteColumn
from rich.progress import TextColumn
from rich.progress import BarColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn
import multiprocessing as mp
from . import config_utilities as cfu
from . import dict_utils as dctu
from .gen_configurations import pipelined_generate_run_params
from .gen_configurations import generate_full_configs
from .acquire_data import pipelined_acquire_data
from .postprocessing_queue import unpack_data, frack_data
from .postprocessing_queue import synchronize_with_config_generation
from itertools import tee, reduce
from copy import deepcopy
from operator import and_


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command()
@click.argument('config', type=click.Path(exists=True),
                metavar='[ROOT CONFIG FILE]')
@click.argument('netcfg', type=click.Path(exists=True),
                metavar='[NERTWORK CONFIG FILE]')
@click.argument('procedure', type=str,
                metavar='[PROCEDURE NAME]')
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[OUTPUT DIRECTORY]')
@click.option('--log', '-l', type=str, default='daq.log',
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', '-v', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
@click.option('--root/--no-root', default=False,
              help='keep the rootfile generated as intermediary')
@click.option('--full_conf_generators', '-f', type=int, default=2,
              help='set how many full-cfg generators to run, default 1')
@click.option('--unpack_tasks', '-u', default=2, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--frack_tasks', '-f', default=7, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--compression', '-c', default=2, type=int,
              help='Set the compression for the hdf file, 0 = no compression'
                   ' 9 = best compression')
@click.option('--keep/--no-keep', default=False,
              help='Keep the already aquired data, defaults to False')
@click.option('--readback/--no-readback', default=False,
              help='Tell the sc-server to read back the register value'
                   'written to the roc')
def main(config, netcfg, procedure, output_dir, log, loglevel,
         root, full_conf_generators, unpack_tasks, fracker_tasks,
         compression, keep, readback):
    config = click.format_filename(config)
    # generate the conifgurations
    if log:
        logging.basicConfig(filename='gen_config.log', level=loglevel,
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    config = click.format_filename(config)
    try:
        procedure, (system_default_config, system_init_config, run_configs,
                    run_count) = cfu.get_procedure_configs(
                            main_config_file=config,
                            procedure_name=procedure,
                            calibration=None,
                            diff=True)
        run_configs_1, run_configs_2 = tee(run_configs)
    except ValueError as err:
        print(f"The procedure with name: {err.args[1]} could not be found,")
        print("Available procedures are:")
        for pname in err.args[2]:
            print(f"\t {pname}")
        exit(1)

    # create the output directory and the initial files
    output_dir = Path(output_dir)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # clean the output directory of any previous config files
    for file in glob.glob(str(output_dir.absolute() / '*.yaml')):
        os.remove(file)

    # generate the initial, default and network config
    netcfg = Path(netcfg)
    shutil.copyfile(netcfg, output_dir / 'network_config.yaml')
    with open(output_dir / 'default_config.yaml', 'w+') as dcf:
        dcf.write(yaml.safe_dump(system_default_config))
    with open(output_dir / 'initial_state_config.yaml', 'w+') as icf:
        icf.write(yaml.safe_dump(system_init_config))
    with open(output_dir / 'postprocessing_config.yaml', 'w+') as pcf:
        post_config = {}
        post_config['data_columns'] = procedure['data_columns']
        post_config['mode'] = procedure['mode']
        post_config['procedure'] = procedure['name']
        pcf.write(yaml.safe_dump(post_config))

    # get the data needed for the postprocessing
    raw_data = True if procedure['mode'] == 'full' else False
    data_columns = procedure['data_columns']

    # generate the configurations for the runs
    num_digits = math.ceil(math.log(run_count, 10))
    full_config = dctu.update_dict(system_default_config, system_init_config)

    # event telling all the subprocesses to stop
    stop = mp.Event()
    # lock to make the tee iterator thread safe
    config_iter_lock = threading.Lock()

    # ##################### DATA QUEUES #########################
    # queue that holds the filenames for a run indicating the
    # run config has been generated
    run_config_queue = queue.Queue()
    # queues containing the run configs for the different full config
    # generators
    full_config_generator_input_queues = \
        [mp.Queue() for _ in range(full_conf_generators)]
    # queue holding the tasks representing the task after
    # data taking
    raw_data_queue = queue.Queue()
    # queue holding the data structure representing tasks
    # after the unpacking
    root_data_queue = queue.Queue()
    # queue holding the tasks representing tasks that
    # have both a full run config on disk and unpacked
    # data. This synchronizes both tasks with each other
    syncronized_root_data_queue = queue.Queue()
    # queue holding the names of the full configurations
    # that have been generated
    full_configs_queue = mp.Queue()
    # list that the queue will be emptied into
    full_configs_queue = []

    # ###################### PROGRESS QUEUES ###################
    # queue for sending infos to the progress bar
    # about the state of run config generation
    run_config_gen_progress_queue = queue.Queue()
    # queue showing the progress of the full run configuration
    full_config_generation_progress = mp.Queue()
    # queue holding tokens symbolizing progress
    # of the daq procedure
    daq_progress = queue.Queue()
    # queue holding tokens symbolizing progress
    # of the unpacking step
    unpack_progress = queue.Queue()
    # queue holding tokens symbolizing progress
    # of the fracking step
    frack_progress = queue.Queue()

    # ################## Completion Events ####################
    # evet signalling that the run configurations
    # have been written to disk
    run_config_gen_done = threading.Event()

    # event signalling that all runs have been placed
    # in the queue for full config generation
    config_queue_fill_done = mp.Event()
    # event used to activate the daq progress bar
    daq_system_initialized = threading.Event()
    # events indicating the completion of a given stage for
    # every run of the procedure
    data_acquisition_done = threading.Event()
    unpack_done = threading.Event()
    sync_done = threading.Event()
    fracking_done = threading.Event()

    # events signalling that the different config generators have finished
    # generating configurations
    full_config_generators_done = [
            mp.Event() for _ in range(full_conf_generators)]

    config_gen_thread = threading.Thread(
            target=pipelined_generate_run_params,
            args=(output_dir,
                  run_configs_2,
                  config_iter_lock,
                  run_config_queue,
                  run_config_gen_progress_queue,
                  run_config_gen_done,
                  num_digits
                  )
            )
    full_config_gen_procs = [mp.Process(
            target=generate_full_configs,
            args=(output_dir,
                  rcq,
                  config_queue_fill_done,
                  full_config,
                  num_digits,
                  full_configs_queue,
                  full_config_generation_progress,
                  fcgd,
                  stop
                  )
            ) for rcq, fcgd in zip(full_config_generator_input_queues,
                                   full_config_generators_done)]
    # acquire the data in a separate thread
    daq_thread = threading.Thread(
            target=pipelined_acquire_data,
            args=(run_config_queue,
                  daq_progress,
                  raw_data_queue,
                  run_config_gen_done,
                  daq_system_initialized,
                  data_acquisition_done,
                  stop,
                  netcfg,
                  system_init_config,
                  output_dir,
                  run_count,
                  keep,
                  readback
                  )
            )
    synchronize_with_full_config_generation = threading.Thread(
            target=synchronize_with_config_generation,
            args=(root_data_queue,
                  syncronized_root_data_queue,
                  full_configs_queue,
                  unpack_done,
                  sync_done
                  )
            )

    # initilize the threads
    unpack_thread = threading.Thread(
            target=unpack_data,
            args=(raw_data_queue,
                  unpack_progress,
                  root_data_queue,
                  data_acquisition_done,
                  unpack_done,
                  max(1, unpack_tasks),
                  raw_data
                  )
            )
    frack_thread = threading.Thread(
            target=frack_data,
            args=(syncronized_root_data_queue,
                  frack_progress,
                  unpack_done,
                  fracking_done,
                  max(1, fracker_tasks),
                  raw_data,
                  root,
                  compression,
                  data_columns,
                  )
            )
    config_gen_thread.start()
    for fcgp in full_config_gen_procs:
        fcgp.start()
    daq_thread.start()
    unpack_thread.start()
    synchronize_with_full_config_generation.start()
    frack_thread.start()
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn()) as progress:
        run_progress_bar = progress.add_task(
                'Generating run configurations',
                total=run_count)
        full_progress_bar = progress.add_task(
                'Generating full config for fracker',
                total=run_count)
        i = 0
        run_config = {}
        # current configuration state of the config generator
        generator_config_states = [{} for _ in range(full_conf_generators)]
        while not config_queue_fill_done.is_set() \
                or not run_config_gen_progress_queue.empty() \
                or not run_config_queue.empty() \
                or not run_config_gen_done.is_set()\
                or not reduce(and_, map(lambda x: x.is_set(),
                                        full_config_generators_done)):
            try:
                for j, (rcq, gstate) in enumerate(
                        zip(full_config_generator_input_queues, generator_config_states)):
                    with config_iter_lock:
                        rcf_update = deepcopy(next(run_configs_1))
                    dctu.update_dict(run_config,
                                     rcf_update, in_place=True)
                    new_state = dctu.update_dict(gstate, run_config)
                    rcq.put((i, new_state))
                    i += 1
                    generator_config_states[j] = new_state
            except StopIteration:
                config_queue_fill_done.set()
            try:
                _ = run_config_queue.get(block=False)
            except queue.Empty:
                pass
            while True:
                try:
                    _ = run_config_gen_progress_queue.get(block=False)
                    progress.update(run_progress_bar, advance=1)
                except queue.Empty:
                    break
            while True:
                try:
                    _ = full_configs_queue.get(block=False)
                    progress.update(full_progress_bar, advance=1)
                except queue.Empty:
                    break
            logging.debug(
                    f'{reduce(and_, map(lambda x: x.is_set(), full_config_generators_done))}'
                    ' = state of full config generators')
        progress.refresh()
    config_gen_thread.join()
    for fgp in full_config_gen_procs:
        fgp.join()
