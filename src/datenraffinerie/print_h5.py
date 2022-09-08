import click
import tables
import pandas as pd
from rich import print


@click.command()
@click.argument('hdf-file', type=click.Path(exists=True),
                metavar='[HDF-DATA]')
def show_hdf(hdf_file):
    tb = tables.open_file(hdf_file)
    data = tb.root.data.measurements
    df = pd.DataFrame.from_records(data.read())
    print(df)
