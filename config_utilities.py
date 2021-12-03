import yaml
from pathlib import Path

class ConfigPatchError(Exception):
    def __init__(self, message):
        self.message = message

class ConfigFormatError(Exception):
    def __init__(self, message):
        self.message = message

def load_configuration(config_path):
    """
    load the configuration dictionary from a yaml file
    """
    with open(config_path, 'r') as config_file:
        return yaml.safe_load(config_file.read())


def update_dict(original: dict, update: dict, offset: bool = False):
    """
    update one multi level dictionary with another. If a key does not
    exist in the original, it is created. the updated dictionary is returned

    Arguments:
    original: the unaltered dictionary

    update: the dictionary that will either overwrite or extend the original

    offset: If True, the values in the update dictionary will be interpreted as
            offsets to the values in the original dict. The resulting value will
            be original + update (this will be string concatenation if both the
            original and update values are strings

    Returns:
    updated_dict: the extended/updated dict where the values that do not appear
                  in the update dict are from the original dict, the keys that
                  do appear in the update dict overwrite/extend the values in
                  the original
    """
    original = original.copy()
    for update_key in update.keys():
        if update_key in original.keys():
            if type(original[update_key]) is not type(update[update_key]):
                raise ConfigPatchError(
                        'The type of the patch does not match the '
                        'type of the original value')
            if type(original[update_key]) is dict:
                update_dict(original[update_key], update[update_key])
            else:
                if offset is True:
                    original[update_key] += update[update_key]
                else:
                    original[update_key] = update[update_key]
        else:
            original[update_key] = update[update_key]
    return original


def patch_configuration(config: dict, patch: dict):
    """
    currently only a wrapper function, if tests need to be implemented,
    then this is done here. Also the correct part of the cofiguration
    may be selected
    """
    return update_dict(config, patch)


def parse_scan_config(scan_config_dict, scan_name):
    """
    parse the different entries of the dictionary to create
    the configuration that can be passed to the higher_order_scan function

    The function returns a tuple that can be passed to the higher-order-scan
    """
    # check if any calibrations need to be performed before taking data
    pre_scan_calibration = None
    if 'calibrated' in scan_config_dict.keys() and scan_config_dict['calibrated'] is True:
        if 'calibration_procedure' not in scan_config_dict.keys():
            raise ConfigFormatError("If the scan needs a calibration to"
                                    "execute first, then the "
                                    "'calibration_procedure' must be"
                                    " defined.")
        pre_scan_calibration = scan_config_dict['calibration_procedure']

    # parse the analyses to be performed
    scan_analyses = []
    if 'analyses' in scan_config_dict.keys():
        scan_analyses = scan_config_dict['analyses']

    # parse the scan dimensions
    scan_parameters = []
    if 'scan_parameters' not in scan_config_dict.keys():
        raise ConfigFormatError("There needs to be a 'scan_parameters' list"
                f" in the scan entry {scan_name}")
    for scan_dimension in scan_config_dict['scan_parameters']:
        step = 1
        start = None
        stop = None
        if 'range' not in scan_dimension.keys():
            raise ConfigFormatError("A range must be specified"
                                    " for a scan dimension")
        for k, v in scan_dimension.items():
            if k == 'range':
                for l, w in v.items():
                    if l == 'step':
                        step = w
                    if l == 'start':
                        start = w
                    if l == 'stop':
                        stop = w
        if start is None or stop is None:
            raise ConfigFormatError(f"The Scan configuration {scan_name} is"
                    " malformed. It misses either the start or stop entry for"
                    " one of it's dimensions")
        scan_range = list(range(start, stop, step))
        scan_parameters.append((scan_dimension['key'], scan_range))
    return (scan_parameters, pre_scan_calibration, scan_name, scan_analyses)

def generate_patch_dict_from_key_tuple(keys: list, value):
    keys.reverse()
    patch = {}
    patch[keys[0]] = value
    for key in keys[1:]:
        if isinstance(key, list):
            patch = {key[0]: patch}
            for subkey in key[1:]:
                patch[subkey] = patch[key[0]]
        else:
            patch = {key: patch}
    return patch


def compile_testsuite_configuration(testsuite_config: dict):
    scan_configs = []
    for k, v in testsuite_config.items():
        try:
            if 'scan_parameters' in v.keys():
                scan_configs.append(parse_scan_config(v, k))
        except AttributeError:
            raise ConfigFormatError(
                    'The configuration seems to be malformed.'
                    ' expected %s to be a dict.' % str(v))


def test_parse_scan_config():
    test_fpath = Path('./test_configurations/parse_scan_config.yaml')
    scan_configs = []
    with open(test_fpath, 'r') as test_file:
        test_config = yaml.safe_load(test_file.read())
        for scan in test_config:
            for k, val in scan.items():  # this should have length one
                scan_configs.append(parse_scan_config(val, k))
    assert len(scan_configs[0][0][0][0]) == 3  # number of keys
    assert len(scan_configs) == 2  # number of different scans
    assert len(scan_configs[1][0]) == 2  # number of dimensions in the second scan
    assert scan_configs[0][0][0][0][0] == 'level1_key1'
    assert scan_configs[1][3][0] == 'injection_scan_analysis'


def test_load_config():
    test_fpath = Path('./test_configurations/parse_scan_config.yaml')
    config = load_configuration(test_fpath)
    assert isinstance(config, list)
    assert isinstance(config[0], dict)


def test_config_updater():
    test_fpath = Path('./test_configurations/parse_scan_config.yaml')
    config = load_configuration(test_fpath)
    original = config[0]['injection_scan']
    assert original['calibrated']
    update = {'calibrated': False}
    updated_dict = update_dict(original, update)
    assert original['calibrated']
    assert updated_dict['calibrated'] is False

def test_patch_generator():
    keys = [['k1', 'k2', 'k3'], 'k4', 'k5']
    value = 1
    patch_dict = generate_patch_dict_from_key_tuple(keys, value)
    assert patch_dict['k1']['k4']['k5'] == 1
    assert patch_dict['k2']['k4']['k5'] == 1
    assert patch_dict['k3']['k4']['k5'] == 1
