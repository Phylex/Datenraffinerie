import click
import yaml
import os
import math
import shutil
import glob
from pathlib import Path
import threading
import multiprocessing as mp
import queue
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import MofNCompleteColumn
from rich.progress import TextColumn
from rich.progress import BarColumn
from rich.progress import TimeElapsedColumn, TimeRemainingColumn
from . import config_utilities as cfu
from . import dict_utils as dctu
from itertools import tee
from time import sleep
import logging
from typing import Union


@click.command()
@click.argument('config', type=click.Path(exists=True),
                metavar='[main configuration file]')
@click.argument('netcfg', type=click.Path(exists=True))
@click.argument('procedure', type=str,
                metavar='[Procedure to be run by the datenraffinerie]')
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location to write the configuration files to]')
def generate_configuratons(config, netcfg, procedure, output_dir):
    # generate the conifgurations
    logging.basicConfig(filename='gen_config.log', level='INFO',
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

    # generate the configurations for the runs
    num_digits = math.ceil(math.log(run_count, 10))
    full_config = dctu.update_dict(system_default_config, system_init_config)
    run_param_queue = queue.Queue()
    param_gen_progress_queue = queue.Queue()
    run_config_generation_done = mp.Event()
    run_config_queue = mp.Queue()
    full_configs_generated = mp.Queue()
    full_config_generation_done = mp.Event()
    config_gen_thread = threading.Thread(
            target=pipelined_generate_run_params,
            args=(output_dir,
                  run_configs_1,
                  run_param_queue,
                  param_gen_progress_queue,
                  run_config_generation_done,
                  num_digits
                  )
            )
    full_config_gen_proc = mp.Process(
            target=generate_full_configs,
            args=(output_dir,
                  run_config_queue,
                  run_config_generation_done,
                  full_config,
                  num_digits,
                  full_configs_generated,
                  full_config_generation_done
                  )
            )
    config_gen_thread.start()
    full_config_gen_proc.start()
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
        while not run_config_generation_done.is_set() \
                or not param_gen_progress_queue.empty() \
                or not run_param_queue.empty() \
                or not full_config_generation_done.is_set()\
                or not full_configs_generated.empty():
            try:
                run_config_queue.put(next(run_configs_2))
            except StopIteration:
                pass
            try:
                _ = run_param_queue.get(block=False)
            except queue.Empty:
                pass
            try:
                _ = param_gen_progress_queue.get(block=False)
                progress.update(run_progress_bar, advance=1)
            except queue.Empty:
                pass
            try:
                _ = full_configs_generated.get(block=False)
                progress.update(full_progress_bar, advance=1)
            except queue.Empty:
                pass
            sleep(.05)
    config_gen_thread.join()
    full_config_gen_proc.join()


def generate_full_configs(output_dir: Path,
                          run_configs: mp.Queue,
                          run_config_generation_done: mp.Event,
                          full_init_config: dict,
                          num_digits: int,
                          generated_configs_full_queue: mp.Queue,
                          config_generation_full_done: mp.Event):
    logger = logging.getLogger('run-config-generator')
    full_config = full_init_config
    i = 0
    while not run_configs.empty() or not run_config_generation_done.is_set():
        config = run_configs.get()
        dctu.update_dict(full_config, config, in_place=True)
        full_run_conf_file_name = 'run_{0:0>{width}}_config_full.yaml'.format(
                i, width=num_digits)
        with open(output_dir / full_run_conf_file_name, 'w+') as frcf:
            frcf.write(yaml.safe_dump(full_config))
        generated_configs_full_queue.put(output_dir / full_run_conf_file_name)
        i += 1
        logger.debug(f'{run_configs.empty()} = run_empty')
        logger.debug(
                f'{run_config_generation_done.is_set()} '
                '= config_generation_done')
    config_generation_full_done.set()


def pipelined_generate_run_params(
        output_dir: Path,
        run_configs: list,
        config_queue: queue.Queue,
        config_gen_progress_queue: queue.Queue,
        config_generation_done: Union[mp.Event, threading.Event],
        num_digits: int):
    for i, run_config in enumerate(run_configs):
        run_conf_file_name = \
                'run_{0:0>{width}}_config.yaml'.format(i, width=num_digits)
        full_run_conf_file_name = 'run_{0:0>{width}}_config_full.yaml'.format(
                i, width=num_digits)
        raw_file_name = \
            'run_{0:0>{width}}_data.raw'.format(i, width=num_digits)
        root_file_name = \
            'run_{0:0>{width}}_data.root'.format(i, width=num_digits)
        hdf_file_name = \
            'run_{0:0>{width}}_data.h5'.format(i, width=num_digits)
        run_conf_path = output_dir / run_conf_file_name
        raw_file_path = output_dir / raw_file_name
        root_file_path = output_dir / root_file_name
        hdf_file_path = output_dir / hdf_file_name
        full_run_conf_path = output_dir / full_run_conf_file_name
        with open(run_conf_path, 'w+') as rcf:
            rcf.write(yaml.safe_dump(run_config))
        config_queue.put(
                (run_config,
                 raw_file_path,
                 root_file_path,
                 hdf_file_path,
                 full_run_conf_path)
        )
        config_gen_progress_queue.put(i)
    config_generation_done.set()
