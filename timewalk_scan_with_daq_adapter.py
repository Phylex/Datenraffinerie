"""
timewalk scan that uses the tools and libraries developed for the
datenraffinerie as a trial by fire for them
"""
import os
import datetime
import copy
from pathlib import Path
import yaml
import click
from control_adapter import TargetAdapter
from control_adapter import DAQSystem
import config_utilities as cfu

ROCS = ['roc_s0', 'roc_s1', 'roc_s2']
SCAN_NAME = 'timewalk_scan'

def connect_injector_and_diff_capacitors(channels, gain):
    """
    Setup the internal injection circuit to do the pulse-height scan
    Connect the Internal injection circuit to the differentiating Capacitors

    Depending on the gain connect different capacitors to the Internal injection circuit:
    Gain = 2:
        10pF (HighRange) and the 500fF (LowRange) capacitor
    Gain = 1:
        10pF (HighRange) Capacitor
    Gain = 0:
        500fF (LowRange) Capacitor
    """
    # pre-configure the injection
    gain_map = {2: ['HighRange', 'LowRange'],
                1: ['HighRange'],
                0: ['LowRange']}
    # create a configuration overlay that configures the injection environment
    # connect the internal injection circuit with the capacitor inputs
    patch_key = [ROCS, 'ReferenceVoltage', list(range(2)), 'IntCtest']
    test_mode_patch = cfu.generate_patch(patch_key, 1)
    # connect the capacitors of the channels of interest to the injection circuit
    patch_key = [ROCS, 'ch', channels, gain_map[gain]]
    channel_config_patch = cfu.generate_patch(patch_key, 1)
    return cfu.update_dict(test_mode_patch, channel_config_patch)


def set_calibDAC(height):
    """
    set the step height of the injection circuit for the entire chip
    """
    patch_key = [ROCS, 'sc', 'RefenceVoltage', 'all', 'Calib']
    patch = cfu.generate_patch(patch_key, height)
    return patch


def configure_daq_server_for_injection_scan(number_of_events, bx_offset):
    """
    configure the server side of the daq connection (this includes parameters of the
    data taking process
    configures the periodic generator (there are 8 hardware blocks
    that generate a fastcommand once every orbit
    """
    # configure the number of events to capture per run
    compound_key = ['server', 'NEvents']
    patch = cfu.generate_patch(compound_key, number_of_events)

    # enable fast commands
    patch_key = ['server', 'l1a_enables',
                 ['random_l1a', 'external_l1as', 'block_sequencer']]
    patch = cfu.update_dict(patch, cfu.generate_patch(patch_key, 0))

    # configure the L1A generators
    # L1A generator A and B
    injection_bx = 0x10
    readout_bx = injection_bx + bx_offset
    l1a_generator_settings = {'l1a_generator_settings': [
            {'enable': 1, 'BX': injection_bx, 'flavor': 'CALPULINT'},
            {'enable': 1, 'BX': readout_bx, 'followMode': 'A'},
            {}, {}]}
    patch = cfu.update_dict(patch, l1a_generator_settings)
    return patch


def timewalk_scan(hexaboard, daq_system, run_config):
    """
    perform the timewalk scan.
    expects the hexaboard and daq system pre-loaded with the initial configuration given by
    user on the cli
    """

    # set up all the parameters that will not change during the run
    output_dir = run_config['output_dir']
    phase = run_config['phase_strobe']
    BXoffset = run_config['BXoffset']
    Channels = run_config['injection_channels']
    gain = run_config['gain']  # 0 for low range ; 1 for high range

    # build the patch that configures the daq server part of the daq_system
    daq_system_server_config = configure_daq_server_for_injection_scan(1000, BXoffset)

    # merge the patches together to form the complete daq_system configuration
    daq_system.configure(daq_system_server_config)
    # save the initial configuration of the ROC before starting the scan
    # of the TOA
    with open(Path(output_dir) / 'daq_system_config.yaml', 'w+') as daq_system_config_file:
        yaml.dump(daq_system.server_config, daq_system_config_file)

    hexaboard.resettdc()

    # set up the injection mechanism of the roc
    injector_config_patch = connect_injector_and_diff_capacitors(Channels, gain)
    # configure the phase for the injection for every roc in the config
    phase_strobe_patch = cfu.generate_patch([ROCS, 'Top', '0', 'phase_strobe'], phase)
    # merge the patches
    hexaboard_patch = cfu.update_dict(phase_strobe_patch, injector_config_patch)
    # run the scan and save the intermediate conifguration
    for index, pulseheight in enumerate(run_config['calibDAC']):
        calib_dac_patch = set_calibDAC(pulseheight)
        run_config = cfu.update_dict(hexaboard_patch, calib_dac_patch)
        hexaboard.configure(run_config)
        with open(Path(output_dir) / 'run_' + str(index) + '.yaml', 'w+', encoding='utf-8')\
                as run_conf_file:
            yaml.dump(hexaboard.configuration, run_conf_file)
        daq_system.take_data(output_dir+'/run_'+str(index)+'.raw')


@click.command()
@click.argument('data_dir', type=click.Path(exists=False))
@click.argument('systemConfig', type=click.File('r'))
@click.argument('targetConfig', type=click.File('r'))
@click.argument('targetPowerOnState', type=click.File('r'))
def main(data_dir: click.Path, systemconfig, targetconfig, targetpoweronstate):
    data_dir = Path(data_dir)
    if data_dir.exists() and os.path.isfile(data_dir):
        print("The path chosen for the data directory is occupied by a file, exiting...")
        return
    elif data_dir.exists() and os.path.isdir(data_dir) and len(list(data_dir.glob('*'))) > 0:
        print("The data directory is already full, exititng...")
        return
    elif not data_dir.exists():
        os.makedirs(data_dir)
    output_dir = data_dir

    # connect to the different daq programs to be able to configure them
    systemconfig = yaml.safe_load(systemconfig)
    daq_system = DAQSystem(systemconfig)

    # connect to the hexaboard
    target_power_on_state = yaml.safe_load(targetpoweronstate)
    target_init_config = yaml.safe_load(targetconfig)
    target_config = cfu.update_dict(target_power_on_state, target_init_config)
    hexaboard = TargetAdapter(target_config)

    # configure the run
    run_config = {
        'phase_strobe': 3,
        'BXoffset': 22,
        'gain': 1,
        'injection_channels': [10, 20, 40, 50],
        'calibDAC': list(range(0, 2048, 16)),
        'output_dir': output_dir
    }
    # perform the scan
    timewalk_scan(hexaboard, daq_system, run_config)


if __name__ == "__main__":
    main()
