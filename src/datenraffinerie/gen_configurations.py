import click
import yaml
import os
import math
import shutil
import glob
from progress.bar import Bar
from pathlib import Path
from . import config_utilities as cfu


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
    bar = Bar('generating run configurations'.ljust(50, ' '), max=run_count)
    for i, run_config in enumerate(run_configs):
        run_file_name = \
                'run_{0:0>{width}}_config.yaml'.format(i, width=num_digits)
        with open(output_dir / run_file_name, 'w+') \
                as rcf:
            rcf.write(yaml.safe_dump(run_config))
        bar.next()
    bar.finish()
