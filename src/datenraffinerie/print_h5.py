import click
import tables
import pandas as pd
from rich import print


@click.command()
@click.argument('hdf-file', type=click.Path(exists=True),
                metavar='[HDF-DATA]')
@click.option('-+rows', '-r', type=int, default=None)
def show_hdf(hdf_file, rows):
    tb = tables.open_file(hdf_file)
    data = tb.root.data.measurements
    df = pd.DataFrame.from_records(data.read())
    if rows is not None:
        print(df.head(rows))
    else: 
        print(df)
