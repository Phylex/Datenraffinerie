import pandas as pd
import numpy as np
import pytest
import uproot
import os
import yaml
from pathlib import Path
import subprocess


class AnalysisError(Exception):
    def __init__(self, message):
        self.message = message


def create_measurement_dataframe(data_directory: str,
                                 channels_of_interest: list):
    """
    get the data from the *.root and the metadata from the *.yaml
    files and merge them together into a dataframe.

    This function parses and combines all the data from the root and
    yaml files into a single pandas dataframe. While performing the
    merging, only the channels selected in the *.yaml['chip_params']
    dictionary entry are selected to be merged together. All other
    channels are ignored. The selection of channels happens for each run
    so the channels of different runs may be different. All files are
    merged into a single pandas dataframe.
    """
    runs = []
    data_directory = Path(data_directory)
    rootfiles = [rf for rf in data_directory.iterdir()
            if os.path.splitext(rf)[1] == '.root']
    for rootfile in rootfiles:
        run_config_file = Path(os.path.splitext(rootfile)[0]+'.yaml')
        if run_config_file.is_file():
            run_config = extract_metadata(run_config_file)
            if run_config['keepRawData'] == 1:
                raise NotImplementedError("raw data mode not implemented")
            else:
                run_data = extract_data(rootfile)
            runs.append((run_data, run_config))
        else:
            raise AnalysisError(
                f"There was no {run_config_file} for {rootfile}")
    for i, run in enumerate(runs):
        runs[i] = merge_in_config_params(run[0], run[1])
    for i, run in enumerate(runs):
        runs[i] = split_channels(run, channels_of_interest)

    return (pd.concat([r[0] for r in runs], axis=0),  # the channels
            pd.concat([r[1] for r in runs], axis=0),  # the calib channels
            pd.concat([r[2] for r in runs], axis=0))  # the common mode chans

def split_channels(run_data, plot_channels):
    """
    split the dataset into three different sets, one for the
    normal channels, one for the calibration channels and one for the
    common mode channels.
    Also create the chip-'half' identifier in the data

    From the channels filter out the channels of interest
    """
    channel_data = pd.concat([run_data[run_data['channel'] == chan]
                             for chan in plot_channels])
    channel_data = channel_data[channel_data['channeltype'] == 0]
    channel_data.assign(half=(channel_data.channel//36)+1)
    calibration_channel_data = run_data[run_data['channeltype'] == 100]
    common_mode_data = run_data[run_data['channeltype'] == 1]
    return (channel_data, calibration_channel_data, common_mode_data)


def extract_metadata(run_config_file):
    """
    Interpret the metadata from the yaml file
    """
    with open(run_config_file, 'r') as file:
        meta_Data = yaml.safe_load(file.read())
        run_configuration = meta_Data['run_params']
        return run_configuration


def extract_data(rootfile, raw_data=False):
    """
    Extract the Data from the rootfile and put it
    into a Pandas dataframe
    """
    with uproot.open(rootfile) as rfile:
        if raw_data is False:
            run_data = {}
            ttree = rfile['runsummary/summary;1']
            for cname in ttree.keys():
                run_data[cname] = pd.Series(
                    np.array(ttree[cname].array()),
                    list(range(len(ttree[cname].array()))))
            run_data = pd.DataFrame(run_data)
            return run_data
        else:
            raise NotImplementedError(
                "The extraction of individual events"
                " has not been implemented")


def add_channel_wise_data(measurement_data: pd.DataFrame, complete_config: dict) -> pd.DataFrame:
    """Add channel wise data adds the data from the configuration
    to every channel that is specific to that channel

    :measurement_data: data that was gathered from the chip
    :complete_config: the complete configuration (so the default config with the
                      patch appled that is the measurement configuration
    :returns: a pandas dataframe where a column has been added for each configuration
              parameter that is channel specific the channels are determined by the
              names and types present in the measurement data.
    """
    channel_keys = roc_get_channel_keys(complete_config)
    for key in channel_keys:
        measurement_data[key] = measurement_data.apply(
                lambda x: roc_channel_to_dict(
                    x['chip'],
                    x['channel'],
                    x['channeltype'],
                    complete_config)[key], axis=1)
    return measurement_data


def add_half_wise_data(measurement_data: pd.DataFrame, complete_config: dict) -> pd.DataFrame:
    """add the config information of the chip half that corresponds to the particular
    channel

    :measurement_data: TODO
    :complete_config: TODO
    :returns: TODO

    """
    channel_keys = roc_channel_to_globals(0, 0, 1, complete_config)
    for key in channel_keys:
        measurement_data[key] = measurement_data.apply(
                lambda x: roc_channel_to_globals(
                    x['chip'],
                    x['channel'],
                    x['channeltype'],
                    complete_config)[key], axis=1)
    return measurement_data


def roc_channel_to_dict(chip_id, channel_id, channel_type, complete_config):
    """Map a channel identifier to the correct part of the config

    :chip_id: chip_id from the measurement in range 0,1,2 for LD hexaboard
    :channel_id: the channel number of the channel
    :channel_type: the channel type from the measurement
    :complete_config: the complete config of the chip
    :returns: TODO

    """
    id_map = {0: 'roc_s0', 1: 'roc_s1', 2: 'roc_s2'}
    channel_type_map = {0: 'ch', 1: 'calib', 100: 'cm'}
    return complete_config[id_map[int(chip_id)]]\
        [channel_type_map[int(channel_type)]][int(channel_id)]


def roc_channel_to_globals(chip_id, channel_id, channel_type, complete_config):
    """get the chip-half wise configuration from the 

    :chip_id: TODO
    :channel_id: TODO
    :channel_type: the channel type either a normal channel.
                   calibration channel or common mode channel
    :complete_config: The complete configuration of the chip at time of measurement
    :returns: a dictionary of all global setting for the given channel

    """
    id_map = {0: 'roc_s0', 1: 'roc_s1', 2: 'roc_s2'}
    channel_type_map = {0: 'ch', 1: 'calib', 100: 'cm'}
    roc_global_keys = ['DigitalHalf', 'GlobalAnalog', 'HalfWise', 'MasterTdc', 'ReferenceVoltage']
    channel_type = channel_type_map[channel_type]
    if channel_type == 'ch':
        chip_half = 0 if channel_id < 36 else 1
    if channel_type == 'cm':
        chip_half = 0 if channel_id < 2 else 1
    if channel_type == 'calib':
        chip_half = channel_id
    roc_config = complete_config[id_map[chip_id]]
    result = {}
    for gl_key in roc_global_keys:
        for key, val in roc_config[gl_key][chip_half].items():
            result[key] = val
    return result


def merge_in_config_params(run_data: pd.DataFrame, run_config: dict):
    """
    merge the run_data with the chip parameters for that run

    Note: for the injected_channels chip parameter a column is added
          that is true when the channel was injected into and false
          otherwise.
    """
    run_params = run_config
    for param in run_params.keys():
        if param == 'injection_channels':
            injected_channels = run_params['injection_channels']
            run_data['injected'] = [y in injected_channels
                                    for y in run_data['channel']]
        elif param not in run_data.columns:
            run_param = pd.Series(run_params[param],
                                  index=run_data.index,
                                  name=param)
            run_data = pd.concat([run_data, run_param], axis=1)
    return run_data


@pytest.mark.xfail
def test_extract_data():
    test_root_path = Path('./tests/data/run.root')
    frame = extract_data(test_root_path.resolve())
    expected_columns = ['chip', 'channel', 'channeltype',
                        'adc_median', 'adc_iqr', 'tot_median',
                        'tot_iqr', 'toa_median', 'toa_iqr', 'adc_mean',
                        'adc_stdd', 'tot_mean',
                        'tot_stdd', 'toa_mean', 'toa_stdd', 'tot_efficiency',
                        'tot_efficiency_error', 'toa_efficiency',
                        'toa_efficiency_error']
    for col in expected_columns:
        _ = frame[col]
