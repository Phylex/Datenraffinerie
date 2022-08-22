import click
import yaml
import os
import math
import shutil
import glob
from pathlib import Path
import threading
import queue
import tqdm
from . import config_utilities as cfu
from . import dict_utils as dctu


@click.command()
@click.argument('config', type=click.Path(exists=True),
                metavar='[main configuration file]')
@click.argument('netcfg', type=click.Path(exists=True))
@click.argument('procedure', type=str,
                metavar='[Procedure to be run by the datenraffinerie]')
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location to write the configuration files to]')
@click.option('--diff/--no-diff', default=True,
              help='only write the differences between the initial config and'
                   'the individual runs to the run config files')
def generate_configuratons(config, netcfg, procedure, output_dir, diff):
    # generate the conifgurations
    config = click.format_filename(config)
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
        post_config['diff'] = diff
        pcf.write(yaml.safe_dump(post_config))

    # generate the configurations for the runs
    num_digits = math.ceil(math.log(run_count, 10))
    full_config = dctu.update_dict(system_default_config, system_init_config)
    run_param_queue = queue.Queue()
    param_gen_progress_queue = queue.Queue()
    config_generation_done = threading.Event()
    config_gen_thread = threading.Thread(
            target=pipelined_generate_run_params,
            args=(output_dir,
                  run_configs,
                  full_config,
                  run_param_queue,
                  param_gen_progress_queue,
                  config_generation_done,
                  num_digits
                  )
            )
    config_gen_thread.start()
    progress_bar = tqdm.tqdm(
            total=run_count,
            desc='Generating run configurations',
            unit=' Configurations')
    while not config_generation_done.is_set() \
            or not param_gen_progress_queue.empty() \
            or not run_param_queue.empty():
        try:
            _ = run_param_queue.get(block=False)
        except queue.Empty:
            pass
        try:
            _ = param_gen_progress_queue.get(block=False)
            progress_bar.update(1)
        except queue.Empty:
            pass
    config_gen_thread.join()


def pipelined_generate_run_params(output_dir: Path,
                                  run_configs: list,
                                  full_init_config: dict,
                                  config_queue: queue.Queue,
                                  config_gen_progress_queue: queue.Queue,
                                  config_generation_done: threading.Event,
                                  num_digits: int):
    full_config = full_init_config
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
        dctu.update_dict(full_config, run_config, in_place=True)
        with open(run_conf_path, 'w+') as rcf:
            rcf.write(yaml.safe_dump(run_config))
        with open(full_run_conf_path, 'w+') as frcf:
            frcf.write(yaml.safe_dump(full_config))
        config_queue.put(
                (run_config,
                 raw_file_path,
                 root_file_path,
                 hdf_file_path,
                 full_run_conf_path)
        )
        config_gen_progress_queue.put(i)
    config_generation_done.set()
