"""
Utilities for the use with the handling of the gathered data 
in the datenraffinerie.
"""
from . import config_utilities as cfu
from pathlib import Path
import os
import shutil
import pandas as pd
import numpy as np
import uproot
import tables
from numba import jit


class AnalysisError(Exception):
    def __init__(self, message):
        super().__init__(message)


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


def unpack_raw_data_into_root(in_file_path, out_file_path, raw_data: bool=False):
    """
    'unpack' the data from the raw data gathered into a root file that
    can then be merged with the configuration into a large table
    """
    if raw_data:
        output_type = ' > /dev/null'
    else:
        output_type = ' -t unpacked'
    unpack_command = 'unpack'
    input_file = ' -i ' + str(in_file_path)
    output_command = ' -o ' + str(out_file_path)
    full_unpack_command = unpack_command + input_file + output_command\
        + output_type
    return os.system(full_unpack_command)


def create_empty_hdf_file(filename: str,
                          expectedrows: int,
                          compression: int = 1) -> tables.File:
    compression_filter = tables.Filters(complib='zlib', complevel=1)
    hdf_file = tables.open_file(filename, mode='w', filters=compression_filter)
    data = hdf_file.create_group('/', 'data')
    # create the attributes that are needed for pandas to
    # be able to read the hdf5 file as a dataframe
    data._v_attrs['axis0_variety'] = 'regular'
    data._v_attrs['axis1_variety'] = 'regular'
    data._v_attrs['encoding'] = 'UTF-8'
    data._v_attrs['errors'] = 'strict'
    data._v_attrs['ndim'] = 2
    data._v_attrs['nblocks'] = 0
    data._v_attrs['pandas_type'] = 'frame'
    data._v_attrs['pandas_version'] = '0.15.2'

    axis1 = hdf_file.create_earray(data, 'axis1', tables.IntAtom(),
                                   shape=(0,))
    axis1._v_attrs['kind'] = 'integer'
    axis1._v_attrs['name'] = 'rows'
    axis1._v_attrs['transposed'] = 1

    axis0 = hdf_file.create_earray(data, 'axis0', tables.StringAtom(50),
                                   shape=(0,))
    axis0._v_attrs['kind'] = 'string'
    axis0._v_attrs['name'] = 'columns'
    axis0._v_attrs['transposed'] = 1
    return hdf_file


def add_data_block(column_names: list, data_type, hdf_file: tables.File, group_name: str):
    hdf_group = hdf_file.get_node(f'/{group_name}')
    blockcount = hdf_group._v_attrs['nblocks']
    hdf_group._v_attrs[f'block{blockcount}_items_variety'] = 'regular'
    hdf_group._v_attrs['nblocks'] = blockcount + 1
    block_items = hdf_file.create_array(hdf_group,
                                        f'block{blockcount}_items',
                                        np.array(column_names))
    block_items._v_attrs['kind'] = 'string'
    block_items._v_attrs['name'] = 'N.'
    block_items._v_attrs['transposed'] = 1
    axis0 = hdf_file.get_node(f'/{group_name}/axis0')
    axis0.append(np.array(column_names))

    block_values = hdf_file.create_earray(hdf_group,
                                          f'block{blockcount}_values',
                                          data_type,
                                          shape=(0, len(column_names)))
    block_values._v_attrs['transposed'] = 1
    return block_values


def fill_block(file, group_name, block, data: np.ndarray):
    axis1 = file.get_node(f'/{group_name}/axis1')
    maxindex = len(axis1)
    block.append(np.array(data))
    if maxindex < len(block):
        axis1.append(np.arange(maxindex, len(block)))


def reformat_data(rootfile: str,
                  hdf_file: str,
                  complete_config: dict,
                  raw_data: bool,
                  chunk_length=50000,
                  columns: list = None):
    """ take in the unpacked root data and reformat into an hdf5 file.
    Also add in the configuration from the run.
    """
    hd_file = create_empty_hdf_file(hdf_file, 1000000)

    if raw_data:
        tree_name = 'unpacker_data/hgcroc'
        chan_id_branch_names = ['chip', 'channel', 'half']
    else:
        tree_name = 'runsummary/summary;1'
        chan_id_branch_names = ['chip', 'channel', 'channeltype']
    with uproot.open(rootfile) as rfile:
        # extract the data from the root file
        ttree = rfile[tree_name]
        if columns is not None:
            keys = list(filter(lambda x: x in columns, ttree.keys()))
        else:
            keys = list(ttree.keys())
        root_data = np.array([ttree[key].array() for key in keys]).transpose()
        blk_values = add_data_block(keys, tables.Int32Atom(), hd_file, 'data')
        fill_block(hd_file, 'data', blk_values, root_data)
        hd_file.flush()
        del root_data
        chip_chan_indices = np.array([ttree[key].array() for key in chan_id_branch_names]).transpose()

        # determin the size of the block that holds the configuration
        chan_config = roc_channel_to_dict(complete_config, 0, 0, 1)
        global_config = roc_channel_to_globals(complete_config, 0, 0, 1)
        l1a_config = l1a_generator_settings(complete_config)
        chan_config = cfu.update_dict(chan_config, global_config)
        chan_config = cfu.update_dict(chan_config, l1a_config)
        if columns is not None:
            config_keys = list(filter(lambda x: x in columns,
                                      chan_config.keys()))
        else:
            config_keys = list(chan_config.keys())
        config_blk = add_data_block(config_keys,
                                    tables.Int32Atom(),
                                    hd_file,
                                    'data')

        # merge in the configuration
        add_config_to_dataset(chip_chan_indices, hd_file, config_blk, complete_config,
                              chunk_length, raw_data, columns)
    hd_file.close()


def add_config_to_dataset(chip_chan_indices,
                          file,
                          dataset,
                          complete_config: dict,
                          chunklength: int,
                          raw_data: bool,
                          columns: list = None):
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
    file: tables.File
        the file that the data should be written to
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
    l1a_config = l1a_generator_settings(complete_config)
    chan_config.update(global_config)
    chan_config.update(l1a_config)
    if columns is not None:
        config_keys = list(filter(lambda x: x in columns,
                                  chan_config.keys()))
    else:
        config_keys = list(chan_config.keys())
    chunks = int(len(chip_chan_indices) / chunklength)
    for i in range(chunks):
        chunk_array = np.zeros(shape=(chunklength, len(config_keys)))
        for j in range(chunklength):
            row = chip_chan_indices[i*chunklength+j]
            chip, chan, half_or_type = row[0], row[1], row[2]
            if raw_data:
                chip, chan, chan_type = \
                 compute_channel_type_from_event_data(chip, chan, half_or_type)
            else:
                chan_type = half_or_type
            chan_config.update(roc_channel_to_dict(complete_config,
                                                   chip, chan, chan_type))
            chan_config.update(roc_channel_to_globals(complete_config,
                                                      chip, chan, chan_type))
            if columns is not None:
                chunk_array[j] = np.array(list(map(lambda x: x[1],
                                                   filter(lambda x: x[0] in columns,
                                                          chan_config.items()))))
            else:
                chunk_array[j] = np.array(list(chan_config.values()))
        fill_block(file, 'data', dataset, chunk_array)
        file.flush()
    # add to the configuration to the last of the items that dont fully
    # fill up a chunk
    remaining_items = chip_chan_indices[chunks*chunklength:]
    chunk_array = np.zeros(shape=(len(remaining_items),
                                  len(config_keys)))
    for j, row in enumerate(remaining_items):
        chip, chan, half_or_type = row[0], row[1], row[2]
        if raw_data:
            chip, chan, chan_type = \
                compute_channel_type_from_event_data(chip, chan, half_or_type)
        else:
            chan_type = half_or_type
        chan_config.update(roc_channel_to_dict(complete_config,
                                               chip, chan, chan_type))
        chan_config.update(roc_channel_to_globals(complete_config,
                                                  chip, chan, chan_type))
        if columns is not None:
            chunk_array[j] = np.array(list(map(lambda x: x[1],
                                               filter(lambda x: x[0] in columns,
                                                      chan_config.items()))))
        else:
            chunk_array[j] = np.array(list(chan_config.values()))
    fill_block(file, 'data', dataset, chunk_array)


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
    axis0 = hd_file.root.data.axis0
    nblocks = hd_file.root.data._v_attrs['nblocks']
    chunksize = 50000
    for in_f in in_files:
        in_ax0 = in_f.root.data.axis0
        inblocks = in_f.root.data._v_attrs['nblocks']
        if nblocks != inblocks:
            raise AnalysisError('the number of Blocks must be '
                                'Identical to merge the files')
        for elem, in_elem in zip(axis0, in_ax0):
            if elem != in_elem:
                raise AnalysisError('the columns of the files '
                                    'to be merged must match')

        for i in range(inblocks):
            out_block_items = getattr(hd_file.root.data, f'block{i}_items')
            out_block_values = getattr(hd_file.root.data, f'block{i}_values')
            in_block_items = getattr(in_f.root.data, f'block{i}_items')
            in_block_values = getattr(in_f.root.data, f'block{i}_values')
            for elem, in_elem in zip(out_block_items, in_block_items):
                if elem != in_elem:
                    raise AnalysisError('The items in the '
                                        f'block {i} don\'t match')
            # append the data from the input block to the output block
            chunks = len(in_block_values) // chunksize
            for chunk in range(chunks):
                start = chunk * chunksize
                stop = start + chunksize
                in_data = in_block_values.read(start, stop)
                fill_block(hd_file, 'data', out_block_values, in_data)
            # append the data that did not fill an entire chunk
            start = chunks * chunksize
            stop = len(in_block_values)
            in_data = in_block_values.read(start, stop)
            fill_block(hd_file, 'data', out_block_values, in_data)
        in_f.close()
        hd_file.flush()
    hd_file.close()


@jit(forceobj=True)
def l1a_generator_settings(complete_config: dict) -> dict:
    """add the config information of the chip half that corresponds to the particular
    channel

    :measurement_data: data measured from the rocs
    :complete_config: configuration of the rocs at the time of measurement.
        the half wise parameters of the rocs from this config will be added to every
        channel of the corresponding half in the `measurement_data`
    :returns: the dataframe measurement_data with added columns for the half wise
              parameters
    """
    l1a_config = {}
    l1a_generators = complete_config['daq']["server"]["l1a_generator_settings"]
    for l1a_generator in l1a_generators:
        name = l1a_generator["name"]
        for key,value in l1a_generator.items():
            if key=="name": continue
            if key=="flavor": continue
            if key=="followMode": continue
            output_key = name + "_" + str(key)
            l1a_config[output_key] = value
    return l1a_config


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
    target_subconfig = complete_config['target']
    id_map = {0: 'roc_s0', 1: 'roc_s1', 2: 'roc_s2'}
    channel_type_map = {0: 'ch', 1: 'calib', 100: 'cm'}
    return target_subconfig[id_map[int(chip_id)]]\
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
    target_subconfig = complete_config['target']
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
    roc_config = target_subconfig[id_map[chip_id]]
    result = {}
    for hw_key in half_wise_keys:
        result.update(roc_config[hw_key][chip_half])
    for gl_key in global_keys:
        result.update(roc_config[gl_key][0])
    return result

# this stuff we define for the tests
data_columns = ['chip', 'channel', 'channeltype',
                    'adc_median', 'adc_iqr', 'tot_median',
                    'tot_iqr', 'toa_median', 'toa_iqr', 'adc_mean',
                    'adc_stdd', 'tot_mean',
                    'tot_stdd', 'toa_mean', 'toa_stdd', 'tot_efficiency',
                    'tot_efficiency_error', 'toa_efficiency',
                    'toa_efficiency_error']
expected_columns = [
    'Adc_pedestal', 'Channel_off', 'DAC_CAL_CTDC_TOA', 'DAC_CAL_CTDC_TOT',
    'DAC_CAL_FTDC_TOA', 'DAC_CAL_FTDC_TOT', 'DIS_TDC', 'ExtData',
    'HZ_inv', 'HZ_noinv', 'HighRange', 'IN_FTDC_ENCODER_TOA',
    'IN_FTDC_ENCODER_TOT', 'Inputdac', 'LowRange', 'mask_AlignBuffer',
    'mask_adc', 'mask_toa', 'mask_tot', 'probe_inv',
    'probe_noinv', 'probe_pa', 'probe_toa', 'probe_tot',
    'sel_trig_toa', 'sel_trig_tot', 'trim_inv', 'trim_toa',
    'trim_tot', 'Adc_TH', 'Bx_offset', 'CalibrationSC',
    'ClrAdcTot_trig', 'IdleFrame', 'L1Offset', 'MultFactor',
    'SC_testRAM', 'SelTC4', 'Tot_P0', 'Tot_P1',
    'Tot_P2', 'Tot ', 'Tot_P_Add',
    'Tot_TH0', 'Tot_TH1', 'Tot_TH2', 'Tot_TH3',
    'sc_testRAM', 'Cf', 'Cf_comp', 'Clr_ADC',
    'Clr_ShaperTail', 'Delay40', 'Delay65', 'Delay87',
    'Delay9', 'En_hyst_tot', 'Ibi_inv', 'Ibi_inv_buf',
    'Ibi_noinv', 'Ibi_noinv_buf', 'Ibi_sk', 'Ibo_inv',
    'Ibo_inv_buf', 'Ibo_no ', 'Ibo_noinv_buf',
    'Ibo_sk', 'ON ', 'ON_ref_adc',
    'ON_rtr', 'ON_toa', 'ON_tot', 'Rc',
    'Rf', 'S_inv', 'S_inv_buf',
    'S_noinv', 'S_noinv_buf', 'S_sk', 'SelExtADC',
    'SelRisingEdge', 'dac_pol', 'gain_tot', 'neg',
    'pol_trig_toa', 'range_indac', 'range_inv', 'range_tot',
    'ref_adc', 'trim_vbi_pa', 'trim_vbo_pa', 'BIAS_CAL_DAC_CTDC_P_D',
    'BIAS_CAL_DAC_CTDC_P_EN', 'BIAS_FOLLOWER_CAL_P_CTDC_EN',
    'BIAS_FOLLOWER_CAL_P_D', 'BIAS_FOLLOWER_CAL_P_FTDC_D',
    'BIAS_FOLLOWER_CAL_P_FTDC_EN', 'BIAS_I_CTDC_D',
    'BIAS_I_FTDC_D', 'CALIB_CHANNEL_DLL',
    'CTDC_CALIB_FREQUENCY', 'CTRL_IN_REF_CTDC_P_D',
    'CTRL_IN_REF_CTDC_P_EN', 'CTRL_IN_REF_FTDC_P_D',
    'CTRL_IN_REF_FTDC_P_EN', 'CTRL_IN_SIG_CTDC_P_D',
    'CTRL_IN_SIG_CTDC_P_EN', 'CTRL_IN_SIG_FTDC_P_D',
    'CTRL_IN_SIG_FTDC_P_EN', 'EN_MASTER_CTDC_DLL',
    'EN_MASTER_CTDC_VOUT_INIT', 'EN_MASTER_FTDC_DLL',
    'EN_MASTER_FTDC_VOUT_INIT', 'EN_REF_BG',
    'FOLLOWER_CTDC_EN', 'FOLLOWER_FTDC_EN',
    'FTDC_CALIB_FREQUENCY', 'GLOBAL_DISABLE_TOT_LIMIT',
    'GLOBAL_EN_BUFFER_CTDC', 'GLOBAL_EN_BUFFER_FTDC',
    'GLOBAL_EN_TOT_PRIORITY', 'GLOBAL_EN_TUNE_GAIN_DAC',
    'GLOBAL_FORCE_EN_CLK', 'GLOBAL_FORCE_EN_OUTPUT_DATA',
    'GLOBAL_FORCE_EN_TOT', 'GLOBAL_INIT_DAC_B_CTDC',
    'GLOBAL_LATENCY_TIME', 'GLOBAL_MODE_FTDC_TOA',
    'GLOBAL_MODE_NO_TOT_SUB', 'GLOBAL_MODE_TOA_DIRECT_OUTPUT',
    'GLOBAL_SEU_TIME_OUT', 'GLOBAL_TA_SELECT_GAIN_TOA',
    'GLOBAL_TA_SELECT_GAIN_TOT', 'INV_FRONT_40MHZ',
    'START_COUNTER', 'VD_CTDC_N_D',
    'VD_CTDC_N_DAC_EN', 'VD_CTDC_N_FORCE_MAX',
    'VD_CTDC_P_D', 'VD_CTDC_P_DAC_EN',
    'VD_FTDC_N_D', 'VD_FTDC_N_DAC_EN',
    'VD_FTDC_N_FORCE_MAX', 'VD_FTDC_P_D',
    'VD_FTDC_P_DAC_EN', 'sel_clk_rcg', 'Calib', 'ExtCtest',
    'IntCtest', 'Inv_vref', 'Noinv_vref', 'ON_dac',
    'Refi', 'Toa_vref', 'Tot_vref', 'Vbg_1v',
    'probe_dc', 'probe_dc1', 'probe_dc2', 'BIAS_I_PLL_D',
    'DIV_PLL', 'EN', 'EN_HIGH_CAPA', 'EN_LOCK_CONTROL',
    'EN_PLL', 'EN_PhaseShift', 'EN_RCG', 'EN_REF_BG',
    'EN_probe_pll', 'ENpE', 'ERROR_LIMIT_SC', 'EdgeSel_T1',
    'FOLLOWER_PLL_EN', 'INIT_D', 'INIT_DAC_EN', 'Pll_Locked_sc',
    'PreL1AOffset', 'RunL', 'RunR', 'S',
    'TestMode', 'VOUT_INIT_EN', 'VOUT_INIT_EXT_D', 'VOUT_INIT_EXT_EN',
    'b_in', 'b_out', 'err_countL', 'err_countR',
    'fc_error_count', 'in_inv_cmd_rx', 'lock_count', 'n_counter_rst',
    'phase_ck', 'phase_strobe', 'rcg_gain', 'sel_40M_ext',
    'sel_error', 'sel_lock', 'sel_strobe_ext', 'srout',
    'statusL', 'statusR', 'Tot_P3', 'Ibo_noinv', 'ON_pa'
    ]

daq_columns = ['Bx_trigger',
               'A_enable',
               'B_enable',
               'C_enable',
               'D_enable',
               'A_BX',
               'B_BX',
               'C_BX',
               'D_BX',
               'A_length',
               'B_length',
               'C_length',
               'D_length',
               'A_prescale',
               'B_prescale',
               'C_prescale',
               'D_prescale',
               ]

def test_extract_data():
    test_root_path = Path('../../tests/data/test_run_1.root')
    unpack_raw_data_into_root('../../tests/data/test_run_1.raw', test_root_path)
    frame = extract_data(test_root_path.resolve())
    for col in data_columns:
        _ = frame[col]


def test_reformat_data():
    """ test that all the channel wise parameters appear as a
    column in the dataframe
    """
    from . import config_utilities as cfu
    
    raw_data_path = Path('../../tests/data/test_run_1.raw')
    root_data_path = Path('./test_run_1.root')
    unpack_raw_data_into_root(raw_data_path, root_data_path, False)
    test_hdf_path = Path('./test_run_1.hdf5')

    # load the configuration of the target for the run
    configuration = cfu.load_configuration('../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml')
    overlay = cfu.load_configuration('../../tests/data/test_run_1.yaml')

    # load the daq config and merge everything together
    daq_config = cfu.load_configuration('../../tests/configuration/defaults/daq-system-config.yaml')
    configuration = cfu.update_dict(configuration, overlay)
    configuration = {'target': configuration, 'daq': daq_config}

    # run the function under test
    reformat_data(root_data_path, test_hdf_path, configuration, False)

    # check that the columns from the config show up in the dataframe
    test_df = pd.read_hdf(test_hdf_path)
    for col in test_df.columns:
        assert col in expected_columns + data_columns + daq_columns
    os.remove(test_hdf_path)

    filtered_columns = ['toa_stdd', 'chip', 'channel', 'channeltype', 'toa_mean',
                        'A_BX', 'HighRange', 'LowRange']
    filter_columns_not_in_data = ['this', 'that']
    reformat_data(root_data_path, test_hdf_path, configuration, False,
                  1000, filtered_columns + filter_columns_not_in_data)
    test_df = pd.read_hdf(test_hdf_path)
    for col in filtered_columns:
        assert col in test_df.columns
    assert test_df.shape[1] == len(filtered_columns)
    os.remove(test_hdf_path)
    os.remove(root_data_path)


def test_merge_files():
    import glob
    from . import config_utilities as cfu
    default_target_config = cfu.load_configuration(
       '../../tests/configuration/defaults/V3LDHexaboard-poweron-default.yaml')
    daq_system_config = cfu.load_configuration(
       '../../tests/configuration/defaults/daq-system-config.yaml')
    default_config = {'target': default_target_config,
                      'daq': daq_system_config}
    raw_files = glob.glob('../../tests/data/*.raw')
    base_names = [os.path.splitext(raw_file)[0] for raw_file in raw_files]
    raw_files = [Path(raw_f) for raw_f in raw_files]
    config_names = [Path(bn + '.yaml') for bn in base_names]
    root_names = [Path(bn + '.root') for bn in base_names]
    dataframe_names = [Path(bn + '.hdf5') for bn in base_names]

    total_rows = 0
    columns = len(data_columns + expected_columns + daq_columns)
    for rawf, rootf, conff, dataff in \
            zip(raw_files, root_names, config_names, dataframe_names):
        unpack_raw_data_into_root(rawf, rootf, False)
        run_config = cfu.load_configuration(conff)
        run_config = cfu.update_dict(default_config, run_config)
        reformat_data(str(rootf.absolute()),
                      str(dataff.absolute()),
                      run_config, False, 1000)
        df_shape = pd.read_hdf(dataff).shape
        total_rows += df_shape[0]
        # assert df_shape[1] == columns

    out_file = 'merged.hdf5'
    merge_files(dataframe_names, out_file, 'data')
    final_df_shape = pd.read_hdf(out_file).shape
    assert final_df_shape[0] == total_rows
    # assert final_df_shape[1] == columns
    for rootf in root_names:
        if rootf.exists():
            os.remove(rootf)
    for df_path in dataframe_names:
        if df_path.exists():
            os.remove(df_path)
    os.remove(out_file)
