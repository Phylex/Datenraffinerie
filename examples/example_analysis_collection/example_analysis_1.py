from pathlib import Path
import pandas as pd
import numpy as np
import scipy.optimize as scopt
import time

# global variables can be used and are only visible to the analysis class
# and anything else defined in this file
SIGNAL_THRESH = 400

# helper functions can also be defined here but are again only accessible
# to objects defined inside this file
def example_helper_1(some_input):
    """ An example helper that does some work and can be used
    anywhere inside the Analysis class, using helper functions
    is a good way to keep the code organized and readable
    """
    print('doing some work here')
    time.sleep(3)
    return 'some_result'


class ExampleAnalysis1(object):

    """This analysis is an example analysis that shows
    the calling convention used by the Datenraffinerie.
    This analysis does not perform any useful work but can
    be used as a Guide to implement the other analyses.
    """

    def __init__(self, analysis_parameters):
        """Initialize the analyses with the parameters from
        the configuration. (The configuration is parsed and
        processed by the Datenraffinerie, so here we get a
        Dictionary with the parameters of the corresponding
        configuration entry.

        :analysis_parameters: A dictionary containing the parameters
        from the analysis configuration

        """
        self._analysis_parameters = analysis_parameters


    def output(self):
        """ Declare the files that constitute the output of the analysis

        :returns: dict containing three entries, The 'summary' entry is a
        path to a summary file, the 'plots' entry is a list of paths (str) to
        the plots produced by the analysis and the 'calibration' entry is a path
        to a calibration configuration that can be used to update existing
        configurations with the calibration obtained from the data.
        A calibration is not mandatory (nor are any of the other files) except
        for analyses that are used explicitly as calibration analyses.
        """
        
        return {
            'summary': 'summary.csv'#,
            #'plots': ['plot1.png','plot2.png'],
            #'calibration': 'calibration.yaml'
        }

    def run(self, data: pd.DataFrame, output_dir: Path):
        """ Perform the analysis in this function. don't forget to create the all
        the files and directories in the return value of the `output` function
        the parameters passed into the object during creation can be used to determin
        various things during the analysis but are not used here

        the code in this function is an example for how an analysis could look like
        without actually being an analysis of any kind

        :data: The pandas Dataframe containing all the chip parameters and measurement
            results of the entire daq process the format of the Dataframe will be described
            in the README/Wiki of the Datenraffinerie
        :output_dir: the directory that the output plots and summaries should be placed
            into. the outputs of the analysis should be exclusively places in this folder
            as not to upset any of the other analyses or acquisition processes.
        """
        signal_channels = data[['chip', 'channel', 'adc_mean']].where(
                data['adc_mean'] > SIGNAL_THRESH).where(
                        data['channeltype'] == 0).dropna()
        plot_data = []
        example_helper_1(data)
        for chan, chip in zip(set(signal_channels['channel']),
                              set(signal_channels['chip'])):
            channel_data = signal_channels.where(
                    signal_channels['chip'] == chip).where(
                            signal_channels['channel'] == chan).dropna()
            plot_data.append((chip, chan, channel_data['adc_mean'].mean()))
        with open(output_dir + self.output()['summary']) as summary:
            summary.write('chip,channel,total_adc_mean\n')
            for elem in plot_data:
                for item in elem:
                    summary.write(str(item) + ',')
                summary.write('\n')
