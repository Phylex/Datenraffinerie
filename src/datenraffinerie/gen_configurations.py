import click
import yaml
import os
from pathlib import Path
from . import config_utilities as cfu
from . import config_validators as cvd
from . import dict_utils as dtu


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
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    config = click.format_filename(config)
    cvd.set_current_path(os.path.dirname(config))
    with open(config, 'r') as cfp:
        config = yaml.safe_load(cfp.read())
    config = cvd.main_config.validate(config)
    available_procedures = config['procedures'] + config['libraries']
    available_procedures = available_procedures[0]
    try:
        procedure = list(filter(lambda x: x['name'] == procedure,
                                available_procedures))[0]
    except IndexError:
        all_procedure_names = list(map(lambda x: x['name'],
                                   available_procedures))
        print(f"The procedure with name: {procedure} could not be found,")
        print("Available procedures are:")
        for pname in all_procedure_names:
            print(f"\t {pname}")
        exit(1)
    system_default_config = cfu.generate_system_default_config(procedure)
    output_dir = Path(output_dir)
    with open(output_dir / 'default_config.yaml', 'w+') as dcf:
        dcf.write(yaml.safe_dump(system_default_config))
    system_init_config = cfu.generate_init_config(procedure)
    full_system_init_config = dtu.update_dict(system_default_config,
                                              system_init_config)
    with open(output_dir / 'inital_state_config.yaml', 'w+') as icf:
        icf.write(yaml.safe_dump(full_system_init_config))
    scan_patches = cfu.generate_patches(procedure)
    for i, patch in enumerate(scan_patches):
        patch = {'target': patch}
        fully_qualified_run_config = dtu.update_dict(
                full_system_init_config, patch)
        if diff:
            fully_qualified_run_config = dtu.diff_dict(
                    full_system_init_config, fully_qualified_run_config)
        with open(output_dir / f'config_run_{i}.yaml', 'w+') as rcf:
            rcf.write(yaml.safe_dump(fully_qualified_run_config))
