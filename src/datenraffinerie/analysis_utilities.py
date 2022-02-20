"""
Utilities for the use with the handling of the gathered data 
in the datenraffinerie.
"""
import pandas as pd
import numpy as np
import pytest
import uproot
import tables
import os
import yaml
from pathlib import Path
import subprocess
from numba import jit


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
        return meta_Data['run_params']


def extract_data(rootfile: str, raw_data=False):
    """
    Extract the Data from the rootfile and put it
    into a Pandas dataframe
    """
    if raw_data is False:
        tree_name = 'runsummary/summary;1'
    else:
        tree_name = 'unpacker_data/hgcroc'

    with uproot.open(rootfile) as rfile:
        run_data = {}
        ttree = rfile[tree_name]
        for cname in ttree.keys():
            run_data[cname] = pd.Series(
                np.array(ttree[cname].array()),
                list(range(len(ttree[cname].array()))))
        return pd.DataFrame(run_data)


def reformat_data(rootfile: str, hdf_file: str, complete_config: dict, raw_data: bool, chunk_length=10000):
    """ take in the unpacked root data and reformat into an hdf5 file.
    Also add in the configuration from the run.
    """
    hd_file = tables.open_file(hdf_file, 'w')
    data = hd_file.create_group('/', 'data')
    # create the attributes that are needed for pandas to
    # be able to read the hdf5 file as a dataframe
    data._v_attrs['axis0_variety'] = 'regular'
    data._v_attrs['axis1_variety'] = 'regular'
    data._v_attrs['block0_items_variety'] = 'regular'
    data._v_attrs['block1_items_variety'] = 'regular'
    data._v_attrs['encoding'] = 'UTF-8'
    data._v_attrs['errors'] = 'strict'
    data._v_attrs['ndim'] = 2
    data._v_attrs['nblocks'] = 2
    data._v_attrs['pandas_type'] = 'frame'
    data._v_attrs['pandas_version'] = '0.15.2'

    # get the data from the 
    if raw_data:
        tree_name = 'unpacker_data/hgcroc'
        chan_id_branch_names = ['chip', 'channel', 'half']
    else:
        tree_name = 'runsummary/summary;1'
        chan_id_branch_names = ['chip', 'channel', 'channeltype']
    with uproot.open(rootfile) as rfile:
        # extract the data from the root file
        ttree = rfile[tree_name]
        keys = list(ttree.keys())
        root_data = np.array([ttree[key].array() for key in keys]).transpose()
        total_length = len(root_data)

        # create the hdf5 data structure for pandas
        b0_items = hd_file.create_array('/data', 'block0_items', np.array(keys))
        b0_items._v_attrs['kind'] = 'string'
        b0_items._v_attrs['name'] = 'N.'
        b0_items._v_attrs['transposed'] = 1

        axis1 = hd_file.create_earray('/data', 'axis1', tables.IntAtom(),
                                      shape=(0,),
                                      expectedrows=total_length)
        axis1.append(np.array(range(total_length)))
        axis1._v_attrs['kind'] = 'integer'
        axis1._v_attrs['name'] = 'N.'
        axis1._v_attrs['transposed'] = 1

        # fill the data from the root file into the hdf5
        b0_values = hd_file.create_earray('/data', 'block0_values',
                                          atom=tables.Float32Atom(len(keys)),
                                          shape=(0,),
                                          expectedrows=total_length)
        b0_values.append(root_data)
        b0_values._v_attrs['transposed'] = 1
        hd_file.flush()

        # determin the size of the block that holds the configuration
        chan_config = roc_channel_to_dict(complete_config, 0, 0, 1)
        global_config = roc_channel_to_globals(complete_config, 0, 0, 1)
        chan_config.update(global_config)
        config_atom = tables.Int32Atom(shape=len(chan_config.values()))

        # create the rest of the needed data structures for the pandas dataframe
        for key in chan_config.keys():
            keys.append(key)
        axis0 = hd_file.create_array('/data', 'axis0', np.array(keys))
        axis0._v_attrs['kind'] = 'string'
        axis0._v_attrs['name'] = 'N.'
        axis0._v_attrs['transposed'] = 1
        b1_items = hd_file.create_array('/data', 'block1_items',
                                        np.array([str(k) for k in chan_config.keys()]))
        b1_items._v_attrs['kind'] = 'string'
        b1_items._v_attrs['name'] = 'N.'
        b1_items._v_attrs['transposed'] = 1

        # create the 2D array with every row being the chip channel and  (half|channeltype)
        chan_id_branches = np.array([ttree[branch_name].array()
                                     for branch_name in chan_id_branch_names],
                                    dtype=np.int32).transpose()
        conf_dset = hd_file.create_earray('/data',
                                          'block1_values',
                                          atom=config_atom,
                                          shape=(0,),
                                          expectedrows=len(chan_id_branches))
        conf_dset._v_attrs['transposed'] = 1
        # merge in the configuration
        add_config_to_dataset(chan_id_branches, conf_dset, complete_config, raw_data)


@jit()
def add_config_to_dataset(chip_chan_indices, dataset, complete_config: dict, raw_data: bool):
    """ generate a single row of the configuration to load into the
    merge into the hdf5 file
    """
    for row in chip_chan_indices:
        chip, chan, half_or_type = row[0], row[1], row[2]
        if raw_data:
            chip, chan, chan_type = compute_channel_type_from_event_data(chip,
                                                                         chan,
                                                                         half_or_type)
        else:
            chip, chan, chan_type = (chip, chan, half_or_type)
        chan_config = roc_channel_to_dict(complete_config, chip, chan, chan_type)
        global_config = roc_channel_to_globals(complete_config,
                                               chip, chan, chan_type)
        chan_config.update(global_config)
    dataset.append(np.array([np.array(list(chan_config.values()))]))


def merge_files(in_files: str, out_file: str, group_name='data'):
    """ take multiple hdf5 files from the individual runs and merge them together into a single
    file
    """
    out_f = h5py.File(out_file, 'w')
    in_files = [h5py.File(in_f, 'r') for in_f in in_files]
    o_data = out_f.create_group(group_name)
    axis0 = list(in_files[0][group_name]['axis0'])
    total_length = sum([len(in_f[group_name]['axis1']) for in_f in in_files])
    o_data.create_dataset('axis0', data=axis0, dtype='|S50')
    o_data.create_dataset('axis1', data=range(total_length), dtype='i4')
    dataset_names = [('block0_items', 'block0_values'),
                     ('block1_items', 'block0_values')]
    dataset_type = ['f4', 'i4']
    datasets = []
    ds_keys = []
    for names, typ in zip(dataset_names, dataset_type):
        keys = list(in_files[0][group_name][names[0]])
        o_data.create_dataset(names[0], data=keys, dtype='|S50')
        ds_keys.append(keys)
        datasets.append(o_data.create_dataset(names[1],
                                              shape=(len(keys), total_length),
                                              chunks=(len(keys), 10000 if total_length > 10000 else total_length),
                                              dtype=typ))
    counters = [0 for _ in ds_keys]
    for in_f in in_files:
        in_axis0 = list(in_f[group_name]['axis0'])
        if in_axis0 != axis0:
            raise ValueError('The axis of the files dont match')
        for counter, keys, (key_name, val_name)\
                in zip(counters, ds_keys, dataset_names):
            in_keys = list(in_f[group_name][key_name])
            if in_keys != keys:
                raise ValueError(
                        f'The {dataset_names[0]} items are misalligned')
            for chunk in in_f[group_name][val_name].iter_chunks():
                for row in chunk:
                    o_data[val_name][counter] = row
                    counter += 1
        in_f.close()
    out_f.close()


def compute_channel_type_from_event_data(chip, channel, half):
    if channel <= 35:
        out_channel = channel * (half + 1)
        out_type = 0
    if channel == 36:
        out_channel = half
        out_type = 1
    if channel > 36:
        out_channel = channel - 37 + (half * 2)
        out_type = 100
    return chip, out_channel, out_type


def roc_channel_to_dict(complete_config, chip_id, channel_id, channel_type):
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


def roc_channel_to_globals(complete_config, chip_id, channel_id, channel_type):
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
    half_wise_keys = ['DigitalHalf', 'GlobalAnalog', 'MasterTdc', 'ReferenceVoltage']
    global_keys = ['Top']
    channel_type = channel_type_map[channel_type]
    if channel_type == 'ch':
        chip_half = 0 if channel_id < 36 else 1
    if channel_type == 'cm':
        chip_half = 0 if channel_id < 2 else 1
    if channel_type == 'calib':
        chip_half = channel_id
    roc_config = complete_config[id_map[chip_id]]
    result = {}
    for hw_key in half_wise_keys:
        for key, val in roc_config[hw_key][chip_half].items():
            result[key] = val
    for gl_key in global_keys:
        for key, val in roc_config[gl_key][0].items():
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


def test_extract_data():
    test_root_path = Path('../../tests/data/run.root')
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


def test_add_channel_wise_data():
    """ test that all the channel wise parameters appear as a
    column in the dataframe
    """
    from . import config_utilities as cfu
    test_data_path = Path('../../tests/data/run.root')
    frame = extract_data(test_data_path.resolve())
    configuration = cfu.load_configuration('../../tests/data/default.yaml')
    overlay = cfu.load_configuration('../../tests/data/run.yaml')
    configuration = cfu.update_dict(configuration, overlay)
    frame = add_channel_wise_data(frame, configuration)
    expected_columns = ['Adc_pedestal',
                        'Channel_off',
                        'DAC_CAL_CTDC_TOA',
                        'DAC_CAL_CTDC_TOT',
                        'DAC_CAL_FTDC_TOA',
                        'DAC_CAL_FTDC_TOT',
                        'DIS_TDC',
                        'ExtData',
                        'HZ_inv',
                        'HZ_noinv',
                        'HighRange',
                        'IN_FTDC_ENCODER_TOA',
                        'IN_FTDC_ENCODER_TOT',
                        'Inputdac',
                        'LowRange',
                        'mask_AlignBuffer',
                        'mask_adc',
                        'mask_toa',
                        'mask_tot',
                        'probe_inv',
                        'probe_noinv',
                        'probe_pa',
                        'probe_toa',
                        'probe_tot',
                        'sel_trig_toa',
                        'sel_trig_tot',
                        'trim_inv',
                        'trim_toa',
                        'trim_tot'
                       ]
    for col in expected_columns:
        print(col, frame[col])


def test_add_half_wise_data():
    """test that all the half_wise parameters are added to the dataframe
    :returns: Nothing

    """
    from . import config_utilities as cfu
    test_data_path = Path('../../tests/data/run.root')
    frame = extract_data(test_data_path.resolve())
    default = cfu.load_configuration('../../tests/data/default.yaml')
    overlay = cfu.load_configuration('../../tests/data/run.yaml')
    config = cfu.update_dict(default, overlay)
    frame = add_half_wise_data(frame, config)
    expected_columns = [
            'Adc_TH',
            'Bx_offset',
            'CalibrationSC',
            'ClrAdcTot_trig',
            'IdleFrame',
            'L1Offset',
            'MultFactor',
            'SC_testRAM',
            'SelTC4',
            'Tot_P0',
            'Tot_P1',
            'Tot_P2',
            'Tot_P3',
            'Tot_P_Add',
            'Tot_TH0',
            'Tot_TH1',
            'Tot_TH2',
            'Tot_TH3',
            'sc_testRAM',
            'Cf',
            'Cf_comp',
            'Clr_ADC',
            'Clr_ShaperTail',
            'Delay40',
            'Delay65',
            'Delay87',
            'Delay9',
            'En_hyst_tot',
            'Ibi_inv',
            'Ibi_inv_buf',
            'Ibi_noinv',
            'Ibi_noinv_buf',
            'Ibi_sk',
            'Ibo_inv',
            'Ibo_inv_buf',
            'Ibo_noinv',
            'Ibo_noinv_buf',
            'Ibo_sk',
            'ON_pa',
            'ON_ref_adc',
            'ON_rtr',
            'ON_toa',
            'ON_tot',
            'Rc',
            'Rf',
            'S_inv',
            'S_inv_buf',
            'S_noinv',
            'S_noinv_buf',
            'S_sk',
            'SelExtADC',
            'SelRisingEdge',
            'dac_pol',
            'gain_tot',
            'neg',
            'pol_trig_toa',
            'range_indac',
            'range_inv',
            'range_tot',
            'ref_adc',
            'trim_vbi_pa',
            'trim_vbo_pa',
            'BIAS_CAL_DAC_CTDC_P_D',
            'BIAS_CAL_DAC_CTDC_P_EN',
            'BIAS_FOLLOWER_CAL_P_CTDC_EN',
            'BIAS_FOLLOWER_CAL_P_D',
            'BIAS_FOLLOWER_CAL_P_FTDC_D',
            'BIAS_FOLLOWER_CAL_P_FTDC_EN',
            'BIAS_I_CTDC_D',
            'BIAS_I_FTDC_D',
            'CALIB_CHANNEL_DLL',
            'CTDC_CALIB_FREQUENCY',
            'CTRL_IN_REF_CTDC_P_D',
            'CTRL_IN_REF_CTDC_P_EN',
            'CTRL_IN_REF_FTDC_P_D',
            'CTRL_IN_REF_FTDC_P_EN',
            'CTRL_IN_SIG_CTDC_P_D',
            'CTRL_IN_SIG_CTDC_P_EN',
            'CTRL_IN_SIG_FTDC_P_D',
            'CTRL_IN_SIG_FTDC_P_EN',
            'EN_MASTER_CTDC_DLL',
            'EN_MASTER_CTDC_VOUT_INIT',
            'EN_MASTER_FTDC_DLL',
            'EN_MASTER_FTDC_VOUT_INIT',
            'EN_REF_BG',
            'FOLLOWER_CTDC_EN',
            'FOLLOWER_FTDC_EN',
            'FTDC_CALIB_FREQUENCY',
            'GLOBAL_DISABLE_TOT_LIMIT',
            'GLOBAL_EN_BUFFER_CTDC',
            'GLOBAL_EN_BUFFER_FTDC',
            'GLOBAL_EN_TOT_PRIORITY',
            'GLOBAL_EN_TUNE_GAIN_DAC',
            'GLOBAL_FORCE_EN_CLK',
            'GLOBAL_FORCE_EN_OUTPUT_DATA',
            'GLOBAL_FORCE_EN_TOT',
            'GLOBAL_INIT_DAC_B_CTDC',
            'GLOBAL_LATENCY_TIME',
            'GLOBAL_MODE_FTDC_TOA',
            'GLOBAL_MODE_NO_TOT_SUB',
            'GLOBAL_MODE_TOA_DIRECT_OUTPUT',
            'GLOBAL_SEU_TIME_OUT',
            'GLOBAL_TA_SELECT_GAIN_TOA',
            'GLOBAL_TA_SELECT_GAIN_TOT',
            'INV_FRONT_40MHZ',
            'START_COUNTER',
            'VD_CTDC_N_D',
            'VD_CTDC_N_DAC_EN',
            'VD_CTDC_N_FORCE_MAX',
            'VD_CTDC_P_D',
            'VD_CTDC_P_DAC_EN',
            'VD_FTDC_N_D',
            'VD_FTDC_N_DAC_EN',
            'VD_FTDC_N_FORCE_MAX',
            'VD_FTDC_P_D',
            'VD_FTDC_P_DAC_EN',
            'sel_clk_rcg',
            'Calib',
            'ExtCtest',
            'IntCtest',
            'Inv_vref',
            'Noinv_vref',
            'ON_dac',
            'Refi',
            'Toa_vref',
            'Tot_vref',
            'Vbg_1v',
            'probe_dc',
            'probe_dc1',
            'probe_dc2',
            'BIAS_I_PLL_D',
            'DIV_PLL',
            'EN',
            'EN_HIGH_CAPA',
            'EN_LOCK_CONTROL',
            'EN_PLL',
            'EN_PhaseShift',
            'EN_RCG',
            'EN_REF_BG',
            'EN_probe_pll',
            'ENpE',
            'ERROR_LIMIT_SC',
            'EdgeSel_T1',
            'FOLLOWER_PLL_EN',
            'INIT_D',
            'INIT_DAC_EN',
            'Pll_Locked_sc',
            'PreL1AOffset',
            'RunL',
            'RunR',
            'S',
            'TestMode',
            'VOUT_INIT_EN',
            'VOUT_INIT_EXT_D',
            'VOUT_INIT_EXT_EN',
            'b_in',
            'b_out',
            'err_countL',
            'err_countR',
            'fc_error_count',
            'in_inv_cmd_rx',
            'lock_count',
            'n_counter_rst',
            'phase_ck',
            'phase_strobe',
            'rcg_gain',
            'sel_40M_ext',
            'sel_error',
            'sel_lock',
            'sel_strobe_ext',
            'srout',
            'statusL',
            'statusR',
           ]
    for col in expected_columns:
        print(frame[col])
