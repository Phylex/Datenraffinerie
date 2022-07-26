import click
import yaml
import os
from pathlib import Path
from . import config_utilities as cfu


@click.command()
@click.argument('config', type=click.Path(exists=True),
                metavar='[main configuration file]')
@click.argument('procedure', type=str,
                metavar='[Procedure to be run by the datenraffinerie]')
@click.argument('output_dir', type=click.Path(dir_okay=True),
                metavar='[Location to write the configuration files to]')
@click.option('--diff', default=False, type=bool,
              help='only write the differences between the initial config and'
                   'the individual runs to the run config files')
def generate_configuratons(config, procedure, output_dir, diff):
    config = click.format_filename(config)
    try:
        system_default_config, system_init_config, run_configs = \
            cfu.get_procedure_configs(main_config_file=config,
                                      procedure_name=procedure,
                                      calibration=None,
                                      diff=diff)
    except ValueError as err:
        print(f"The procedure with name: {err.args[1]} could not be found,")
        print("Available procedures are:")
        for pname in err.args[2]:
            print(f"\t {pname}")
        exit(1)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    output_dir = Path(output_dir)
    with open(output_dir / 'default_config.yaml', 'w+') as dcf:
        dcf.write(yaml.safe_dump(system_default_config))
    with open(output_dir / 'inital_state_config.yaml', 'w+') as icf:
        icf.write(yaml.safe_dump(system_init_config))
    for i, run_config in enumerate(run_configs):
        with open(output_dir / f'config_run_{i}.yaml', 'w+') as rcf:
            rcf.write(yaml.safe_dump(run_config))
