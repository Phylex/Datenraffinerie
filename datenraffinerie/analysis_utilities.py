"""
Utilities for the use with the handling of the gathered data
in the datenraffinerie.
"""
import subprocess as sp
import numpy as np
from pathlib import Path
import os
import shutil
import pandas as pd
import tables
import yaml
import logging


class AnalysisError(Exception):
    def __init__(self, message):
        super().__init__(message)


def cartesian(arrays, dtype=np.float32):
    n = 1
    for i in range(len(arrays)):
        arrays[i] = np.array(arrays[i], dtype=dtype)
    for x in arrays:
        n *= x.size
    out = np.zeros((n, len(arrays)), dtype=dtype)

    for i in range(len(arrays)):
        m = int(n / arrays[i].size)
        out[:n, i] = np.repeat(arrays[i], m)
        n //= arrays[i].size

    n = arrays[-1].size
    for k in range(len(arrays)-2, -1, -1):
        n *= arrays[k].size
        m = int(n / arrays[k].size)
        for j in range(1, arrays[k].size):
            out[j*m:(j+1)*m, k+1:] = out[0:m, k+1:]
    return out


def read_whole_dataframe(pytables_filepath):
    dfile = tables.open_file(pytables_filepath, 'r')
    table = dfile.root.data.measurements
    df = pd.DataFrame.from_records(table.read())
    dfile.close()
    return df


def read_dataframe_chunked(pytables_filepaths):
    for filepath in pytables_filepaths:
        dfile = tables.open_file(filepath)
        table = dfile.root.data.measurements
        yield pd.DataFrame.from_records(table.read())
        dfile.close()


def start_compiled_fracker(rootfile: Path,
                           hdf_file: Path,
                           full_config_path: Path,
                           raw_data: bool,
                           columns: list,
                           compression: int,
                           logger: logging.Logger,
                           block_size: int = 2000000):
    """
    Assuming there is a fracker command that merges in the configuration
    and transforms the root into the hdf file call it with the proper arguments
    """
    compiled_fracker_path = shutil.which('fracker')
    if compiled_fracker_path is None:
        raise FileNotFoundError('The compiled fracker could not be found')
    # build the column list if none has been provided
    if columns is None:
        if raw_data:
            columns = event_mode_data_columns.copy()
        else:
            columns = data_columns.copy()
        columns += expected_columns

    # assemble the fracker command string passed to the system
    fracker_command_tokens = [compiled_fracker_path]
    fracker_command_tokens.append('-c')
    fracker_command_tokens.append(str(full_config_path.absolute()))
    fracker_command_tokens.append('-i')
    fracker_command_tokens.append(str(rootfile.absolute()))
    fracker_command_tokens.append('-o')
    fracker_command_tokens.append(str(hdf_file.absolute()))
    fracker_command_tokens.append('-b')
    fracker_command_tokens.append(str(block_size))
    fracker_command_tokens.append('-s')
    fracker_command_tokens += [str(col) for col in columns]
    fracker_command_tokens.append('-p')
    fracker_command_tokens.append(str(compression))
    fracker_command_tokens.append('-f')
    fracker_command_tokens.append('full' if raw_data else 'summary')
    logger.info(
        'Ran fracker with command: ' + ' '.join(fracker_command_tokens))
    return sp.Popen(fracker_command_tokens, stdout=sp.PIPE)


def run_turbo_pump(output_file: str, input_files: list):
    """
    run the compiled turbo pump to merge files
    """
    turbo_pump_path = shutil.which('turbo-pump')
    tp_output = " -o " + str(output_file)
    tp_input = " -i"
    for inp in input_files:
        tp_input += " " + str(inp)
    full_turbo_p_command = turbo_pump_path + tp_output + tp_input
    return os.system(full_turbo_p_command)


def start_unpack(raw_path,
                 unpacked_path,
                 logger: logging.Logger,
                 raw_data: bool = False,
                 characMode: bool = False):
    # we need to create a meta-yaml file for the unpacker
    meta_yaml_path = os.path.splitext(
            os.path.abspath(unpacked_path))[0] + '_unpack_meta.yaml'
    meta_yaml = {}
    meta_yaml['metaData'] = {}
    meta_yaml['metaData']['characMode'] = 1 if characMode else 0
    meta_yaml['metaData']['keepRawData'] = 1 if raw_data else 0
    meta_yaml['metaData']['keepSummary'] = 0 if raw_data else 1
    meta_yaml['metaData']['chip_params'] = {}
    with open(meta_yaml_path, 'w+') as mcf:
        mcf.write(yaml.safe_dump(meta_yaml))

    unpack_command_path = shutil.which('unpack')
    if unpack_command_path is None:
        raise FileNotFoundError('Unable to find the unpack command')
    unpack_command_tokens = ['unpack']
    # add the input file to the token list
    unpack_command_tokens.append('-i')
    unpack_command_tokens.append(str(raw_path))
    # add the output file to the token list
    unpack_command_tokens.append('-o')
    unpack_command_tokens.append(str(unpacked_path))
    unpack_command_tokens.append('-M')
    unpack_command_tokens.append(str(meta_yaml_path))
    logger.info('starting unpack command: ' + ' '.join(unpack_command_tokens))
    return sp.Popen(unpack_command_tokens, stdout=sp.PIPE)


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


event_mode_data_columns = [
        'event', 'chip', 'half', 'channel', 'adc', 'adcm', 'toa',
        'tot', 'totflag', 'trigtime', 'trigwidth', 'corruption',
        'bxcounter', 'eventcounter', 'orbitcounter']

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
