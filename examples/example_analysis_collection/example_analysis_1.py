from pathlib import Path
import pandas as pd
import numpy as np
import scipy.optimize as scopt
import time

SIGNAL_THRESH = 400

def example_helper_1(some_input):
    print('doing some work here')
    time.sleep(3)
    return 'some_result'

def output():
    """ Declare the files that constitute the output of the analysis

    :returns: list[str] containing the relative paths of the output
    files. The output should only be placed below the '.' directory
    if subdirectories are used they should be created by the run method
    """
    return ['./summary.csv', './plots/plot_1.pdf', './plots/plot_N.pdf']


def run(data: pd.DataFrame, output_dir: Path):
    """ Perform the analysis in this function. don't forget to create the all
    the files and directories in the return value of the `output` function

    the code in this function is an example for how an analysis could look like
    without actually being an analysis of any kind

    :data: The pandas Dataframe containing all the chip parameters and measurement
        results of the entire daq process
    :output_dir: the directory that the output plots and summaries should be placed
        into. the outputs of the analysis should be exclusively places in this folder
        as not to upset any of the other analyses or acquisition processes.
    """
    signal_channels = data[['chip', 'channel', 'adc_mean']].where(data['adc_mean'] > SIGNAL_THRESH).where(data['channeltype'] == 0).dropna()
    plot_data = []
    for chan, chip in zip(set(signal_channels['channel']), set(signal_channels['chip'])):
        channel_data = signal_channels.where(signal_channels['chip'] == chip).where(signal_channels['channel'] ==chan).dropna()
        plot_data.append((chip, chan, channel_data['adc_mean'].mean()))
    with open(output_dir + '/summary.csv') as summary:
        summary.write('chip,channel,total_adc_mean\n')
        for elem in plot_data:
            for item in elem:
                summary.write(str(item) + ',')
            summary.write('\n')
