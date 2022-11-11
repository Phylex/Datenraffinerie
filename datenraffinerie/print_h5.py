import click
import tables
import pandas as pd
from rich import print


@click.command()
@click.argument('hdf-file', type=click.Path(exists=True),
                metavar='[HDF-DATA]')
@click.option('--rows', '-r', type=int, default=50)
@click.option('--start', '-s', type=int, default=0)
def show_hdf(hdf_file, rows, start):
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    tb = tables.open_file(hdf_file)
    data = tb.root.data.measurements
    df = pd.DataFrame.from_records(data.read())
    print(df.iloc[start:start+rows])
