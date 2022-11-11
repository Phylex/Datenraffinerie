import click
import yaml
from rich import print
from hgcroc_configuration_client.client import Client as SCClient
import sys


@click.group("cli")
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo('No command was given to read-rocs. Available commands are:'
                   '\n\tconfigure\n\tread\n\treset\n\tdescribe')


@cli.command()
@click.argument('hostname', type=str,
                metavar='[HOSTNAME]')
@click.argument('port', type=str,
                metavar='[PORT]')
@click.argument('configuration', type=click.File('r'))
@click.option(
        '--readback',
        '-r',
        is_flag=True,
        show_default=True,
        default=False,
        help='read back every parameter written to the '
             'ROC to make sure that the config was written properly')
def configure(hostname, port, configuration, readback):
    sc_client = SCClient(hostname, port=port)
    try:
        config = yaml.safe_load(configuration.read())
    except yaml.ScannerError as err:
        print(f'Could not read in yaml. {err}')
        sys.exit(1)
    try:
        config = config['target']
    except KeyError:
        pass
    try:
        sc_client.set(config, readback=readback)
    except ValueError as err:
        print('An error occured during the writing of '
              f'the configuration: {err}')
        sys.exit(2)
    print('Configuration written to the rocs')


@cli.command()
@click.argument('hostname', type=str,
                metavar='[HOSTNAME]')
@click.argument('port', type=str,
                metavar='[PORT]')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='File that the Config is written is written to. '
                   'If no file is given the output is printed on stdout')
def read(hostname, port, output):
    sc_client = SCClient(hostname, port=port)
    try:
        config = sc_client.get_from_hardware(config=None)
    except ValueError as err:
        print(f'During reading of the ROCs an error occured: {err}')
        sys.exit(3)
    printout = yaml.safe_dump({'target': config})
    if output is None:
        print(printout)
    else:
        with open(output, 'w+') as rcof:
            rcof.write(printout)


@cli.command()
@click.argument('hostname', type=str,
                metavar='[HOSTNAME]')
@click.argument('port', type=str,
                metavar='[PORT]')
def reset(hostname, port):
    sc_client = SCClient(hostname, port=port)
    try:
        sc_client.reset()
    except ValueError as err:
        print(f'During reset an error occured: {err}')
        sys.exit(4)


@cli.command()
@click.argument('hostname', type=str,
                metavar='[HOSTNAME]')
@click.argument('port', type=str,
                metavar='[PORT]')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='File that the description is written is written to. '
                   'If no file is given the output is printed on stdout')
def describe(hostname, port, output):
    sc_client = SCClient(hostname, port=port)
    try:
        description = sc_client.describe()
    except ValueError as err:
        print(f'During the readout of the description an error occured: {err}')
        sys.exit(5)
    printout = yaml.safe_dump({'target': description})
    if output is None:
        print(printout)
    else:
        with open(output, 'w+') as descf:
            descf.write(printout)
