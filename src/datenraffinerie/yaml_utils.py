import click
from . import dict_utils as dctu
import yaml


@click.group("cli")
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo('No command was given to the tool. Available commands are:'
                   '\n\tupdate\n\tdiff')


@cli.command()
@click.argument('original', type=click.File('r'))
@click.argument('patch', type=click.File('r'))
@click.argument('output', type=click.File('w+'))
def update(original, patch, output):
    try:
        orig_dict = yaml.safe_load(original.read())
    except yaml.ScannerError:
        click.echo('The original file is not valid yaml syntax')
        exit(1)
    try:
        update = yaml.safe_load(patch.read())
    except yaml.ScannerError:
        click.echo('The patch file is not valid yaml syntax')
        exit(1)
    output_dict = dctu.update_dict(orig_dict, update)
    if output_dict is None:
        output_dict = {}
    output.write(yaml.safe_dump(output_dict))


@cli.command()
@click.argument('original', type=click.File('r'))
@click.argument('changed', type=click.File('r'))
@click.argument('difference', type=click.File('w+'))
def diff(original, changed, difference):
    try:
        orig_dict = yaml.safe_load(original.read())
    except yaml.ScannerError:
        click.echo('The original file is not valid yaml syntax')
        exit(1)
    try:
        changed_dict = yaml.safe_load(changed.read())
    except yaml.ScannerError:
        click.echo('The patch file is not valid yaml syntax')
        exit(1)
    diff_dict = dctu.diff_dict(orig_dict, changed_dict)
    if diff_dict is None:
        diff_dict = {}
    difference.write(yaml.safe_dump(diff_dict))


if __name__ == '__main__':
    cli()
