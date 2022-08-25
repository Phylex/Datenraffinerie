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
import tqdm
import multiprocessing as mp
from . import config_utilities as cfu
from . import dict_utils as dctu
from .gen_configurations import pipelined_generate_run_params
from .gen_configurations import generate_full_configs
from .acquire_data import pipelined_acquire_data
from .postprocessing_queue import unpack_data, frack_data
from .postprocessing_queue import synchronize_with_config_generation


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command()
@click.argument('config', type=click.Path(exists=True),
                metavar='[ROOT CONFIG FILE]')
@click.argument('netcfg', type=click.Path(exists=True))
@click.argument('procedure', type=str,
                metavar='[PROCEDURE NAME]')
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[OUTPUT DIRECTORY]')
@click.option('--log', '-l', type=str, default=None,
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', '-v', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
@click.option('--root/--no-root', default=False,
              help='keep the rootfile generated as intermediary')
@click.option('--unpack_tasks', '-u', default=1, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--fracker_tasks', '-f', default=3, type=int,
              help='number of unpackers/frackers to run in parallel')
@click.option('--compression', '-c', default=3, type=int,
              help='Set the compression for the hdf file, 0 = no compression'
                   ' 9 = best compression')
@click.option('--keep/--no-keep', default=False,
              help='Keep the already aquired data, defaults to False')
def main(config, netcfg, procedure, output_dir, log, loglevel,
         root, unpack_tasks, fracker_tasks, compression, keep):
    config = click.format_filename(config)
    diff = True
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    logger = logging.getLogger('main')
    try:
        procedure, (system_default_config, system_init_config, run_configs,
                    run_count) = cfu.get_procedure_configs(
                            main_config_file=config,
                            procedure_name=procedure,
                            calibration=None,
                            diff=diff)
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

    # generate the initial, default and network config and store them in the
    # output folder
    netcfg = Path(netcfg)
    shutil.copyfile(netcfg, output_dir / 'network_config.yaml')
    logger.info('Reading in configurations')
    with open(netcfg, 'r') as nwcf:
        network_config = yaml.safe_load(nwcf.read())
    with open(output_dir / 'default_config.yaml', 'w+') as dcf:
        dcf.write(yaml.safe_dump(system_default_config))
    with open(output_dir / 'initial_state_config.yaml', 'w+') as icf:
        icf.write(yaml.safe_dump(system_init_config))

    with open(output_dir / 'postprocessing_config.yaml', 'w+') as pcf:
        post_config = {}
        post_config['data_columns'] = procedure['data_columns']
        post_config['mode'] = procedure['mode']
        post_config['diff'] = diff
        pcf.write(yaml.safe_dump(post_config))

    # setup variables for the postprocessing
    num_digits = math.ceil(math.log(run_count, 10))
    raw_data = True if post_config['mode'] == 'full' else False
    data_columns = procedure['data_columns']
    full_config = dctu.update_dict(system_default_config, system_init_config)

    # threading/pipelining data structures

    # queue to pass the data structure representing the
    # acquired data from one thread to the next
    run_parameter_queue = queue.Queue()
    raw_data_queue = queue.Queue()
    root_data_queue = queue.Queue()
    syncronized_root_data_queue = queue.Queue()
    # events indicating the completion of a given stage for
    # every run of the procedure
    run_config_generation_done = threading.Event()
    full_config_generation_done = mp.Event()
    data_aquisition_done = threading.Event()
    unpack_done = threading.Event()
    sync_done = threading.Event()
    # queue and list storing the filenames for the full configuration
    # that have already been generated
    generated_full_configs_queue = mp.Queue()
    full_configs_generated = []

    run_config_gen_progress = queue.Queue()
    daq_progress = queue.Queue()
    unpack_progress = queue.Queue()
    frack_progress = queue.Queue()

    # set up the threads
    run_param_generator = threading.Thread(
            target=pipelined_generate_run_params,
            args=(output_dir,
                  run_configs,
                  run_parameter_queue,
                  run_config_gen_progress,
                  run_config_generation_done,
                  num_digits)
            )

    full_config_generator = mp.Process(
            target=generate_full_configs,
            args=(output_dir,
                  run_configs,
                  full_config,
                  num_digits,
                  generated_full_configs_queue,
                  full_config_generation_done
                  )
            )

    daq_thread = threading.Thread(
            target=pipelined_acquire_data,
            args=(run_parameter_queue,
                  daq_progress,
                  raw_data_queue,
                  run_config_generation_done,
                  network_config,
                  system_init_config,
                  output_dir,
                  run_count,
                  keep
                  )
            )

    unpack_thread = threading.Thread(
            target=unpack_data,
            args=(raw_data_queue,
                  root_data_queue,
                  data_aquisition_done,
                  max(1, unpack_tasks),
                  logging.getLogger('unpack-coordinator'),
                  raw_data
                  )
            )

    synchronize_with_full_config_generation = threading.Thread(
            target=synchronize_with_config_generation,
            args=(root_data_queue,
                  syncronized_root_data_queue,
                  full_configs_generated,
                  unpack_done,
                  sync_done
                  )
            )

    frack_thread = threading.Thread(
            target=frack_data,
            args=(root_data_queue,
                  unpack_done,
                  max(1, fracker_tasks),
                  logging.getLogger('fracking-coordinator'),
                  raw_data,
                  root,
                  compression,
                  data_columns
                  )
            )

    run_param_generator.start()
    full_config_generator.start()
    daq_thread.start()
    unpack_thread.start()
    synchronize_with_full_config_generation.start()
    frack_thread.start()
