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
import shutil
import subprocess
from numba import jit


class AnalysisError(Exception):
    def __init__(self, message):
        self.message = message


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
    # create a compression filter
    compression_filter = tables.Filters(complib='zlib', complevel=5)
    hd_file = tables.open_file(hdf_file, mode='w', filters=compression_filter)
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
                                          expectedrows=total_length)
        conf_dset._v_attrs['transposed'] = 1
        # merge in the configuration
        add_config_to_dataset(chan_id_branches, conf_dset, complete_config, 10000, raw_data)
    hd_file.close()


@jit()
def add_config_to_dataset(chip_chan_indices, dataset, complete_config: dict, chunklength: int, raw_data: bool):
    """
    Add the configuration to the dataset

    extract the configuration for the chip/channel/type from the complete configuration
    for every row in the data and add it to the 'block1_values' EArray of the hdf5 file

    This function expects that the EArray has been created and all the neccesary metadata written
    it will simply add extract the data and append it to the EArray

    Parameters
    ----------
    chip_chan_indices : numpy.ndarray
        a 2D array where every row corresponds to [chip, channel, half_or_type]
    dataset : tables.EArray
        the EArray that the data needs to be added to
    complete_config : dict
        the complete configuration of the chip at the time of the measurement
    chunklength : int
        the number of rows in a chunk of the hdf file this
    """
    chan_config = roc_channel_to_dict(complete_config, 0, 0, 1)
    global_config = roc_channel_to_globals(complete_config,
                                           0, 0, 1)
    chan_config.update(global_config)
    chunks = int(len(chip_chan_indices) / chunklength)
    for i in range(chunks):
        chunk_array = np.zeros(shape=(chunklength, len(chan_config.items())))
        for j in range(chunklength):
            row = chip_chan_indices[i*chunklength+j]
            chip, chan, half_or_type = row[0], row[1], row[2]
            if raw_data:
                chip, chan, chan_type = compute_channel_type_from_event_data(chip,
                                                                             chan,
                                                                             half_or_type)
            else:
                chan_type = half_or_type
            chan_config = roc_channel_to_dict(complete_config,
                                              chip,
                                              chan,
                                              chan_type)
            global_config = roc_channel_to_globals(complete_config,
                                                   chip, chan, chan_type)
            chan_config.update(global_config)
            chunk_array[j] = np.array(list(chan_config.values()))
        dataset.append(chunk_array)
    # add to the configuration to the last of the items that dont fully
    # fill up a chunk
    remaining_items = chip_chan_indices[chunks*chunklength:]
    chunk_array = np.zeros(shape=(len(remaining_items),
                                  len(chan_config.items())))
    for j, row in enumerate(remaining_items):
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
        chunk_array[j] = np.array(list(chan_config.values()))
    dataset.append(chunk_array)


def merge_files(in_files: list, out_file: str, group_name: str='data'):
    """
    Merge the files of the different runs into a single file containing all
    the data
    """
    start_file = in_files[0]
    in_files = [tables.open_file(in_f, 'r') for in_f in in_files[1:]]
    # compression_filter = tables.Filters(complib='zlib', complevel=5)
    # copy the first of the input files to become the merged output
    shutil.copy(start_file, out_file)
    hd_file = tables.open_file(out_file, mode='r+')
    block0_items = hd_file.root.data.block0_items
    blk0 = hd_file.root.data.block0_values
    block1_items = hd_file.root.data.block1_items
    blk1 = hd_file.root.data.block1_values
    chunksize = 10000
    for in_f in in_files:
        in_blk0 = in_f.root.data.block0_items
        in_blk1 = in_f.root.data.block1_items
        for elem, in_elem in zip(block0_items, in_blk0):
            if elem != in_elem:
                raise AnalysisError('the block0_items of the files to be merged must match')
        for elem, in_elem in zip(block1_items, in_blk1):
            if elem != in_elem:
                raise AnalysisError('the block1_items of the files to be merged must match')
        in_blk0 = in_f.root.data.block0_values
        in_blk1 = in_f.root.data.block1_values
        # append the data for block0
        chunks = len(in_blk0) // chunksize
        for chunk in range(chunks):
            start = chunk * chunksize
            stop = start + chunksize
            blk0.append(in_blk0.read(start, stop))
        blk0.append(in_blk0.read(chunks*chunksize, len(in_blk0)))
        # append the data for block1
        chunks = len(in_blk1) // chunksize
        for chunk in range(chunks):
            start = chunk * chunksize
            stop = start + chunksize
            blk1.append(in_blk1.read(start, stop))
        blk1.append(in_blk1.read(chunks*chunksize, len(in_blk1)))
        in_f.close()


@jit(nopython=True)
def compute_channel_type_from_event_data(chip: int, channel: int, half: int):
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


@jit(nopython=False, forceobj=True)
def roc_channel_to_dict(complete_config: dict, chip_id: int, channel_id: int, channel_type: int) -> dict:
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


def roc_channel_to_globals(complete_config: dict, chip_id: int, channel_id: int, channel_type: int) -> dict:
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


def test_reformat_data():
    """ test that all the channel wise parameters appear as a
    column in the dataframe
    """
    from . import config_utilities as cfu
    test_data_path = Path('../../tests/data/event_run.root')
    test_hdf_path = Path('../../tests/data/event_run.hdf5')
    configuration = cfu.load_configuration('../../tests/data/default.yaml')
    overlay = cfu.load_configuration('../../tests/data/run.yaml')
    configuration.update(overlay)
    reformat_data(test_data_path, test_hdf_path, configuration, True)
    expected_columns = [
        'Adc_pedestal',
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
        'trim_tot',
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
        'statusR']
    df = pd.read_hdf(test_hdf_path)
    for c in df.columns:
        assert c in expected_columns


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
           ]
    for col in expected_columns:
        print(frame[col])
