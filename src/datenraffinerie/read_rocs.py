import click
import yaml
from rich import print
from hgcroc_configuration_client.client import Client as SCClient


@click.command()
@click.argument('hostname', type=str,
                metavar='[HOSTNAME]')
@click.argument('port', type=str,
                metavar='[PORT]')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='File that the Config is written is written to. '
                   'If no file is given the output is printed on stdout')
@click.option('--reset/--no-reset', '-r', type=bool, default=None,
              help='Reset the roc befor reading the conifgs')
def read_rocs(hostname, port, output, reset):
    sc_client = SCClient(hostname, port=port)
    if reset:
        sc_client.reset()
    config = sc_client.get_from_hardware(config=None)
    printout = yaml.safe_dump({'target': config})
    if output is None:
        print(printout)
    else:
        with open(output, 'w+') as rcof:
            rcof.write(printout)
