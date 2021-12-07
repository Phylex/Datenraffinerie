from pathlib import Path
import yaml


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


def diff_dict(d1: dict, d2: dict) -> dict:
    """
    create the diff of two dictionaries.

    Create a dictionary containing all the keys that differ between
    d1 and d2 or that exist in d2 but not in d1. The value of the
    differing key will be the value found in d2.

    Example:
        With the inputs being
        d1 = {'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3}
        d2 = {'a': 2, 'b': {'c': 3, 'f': 4}, 'e': 3, 'g': 4}

        the resulting diff will be
        diff = {'a': 2, 'b': {'c':3}, 'g': 4}

        showing that the keys 'a' and 'b:c' are different and that the
        value in the differing d2 is 2 for a and 3 for 'b:c' respectively.
        As there is an entry in d2 that is not in d1 it will appear in the
        diff, however if there is an entry in d1 that is not in d2 it will
        not appear.

    This function is intended to find the patch that where applied on d1 to
    create d2. This may provide some motivation for the way that the function
    handles the different dictionaries
    """
    diff = {}
    for key2, value2 in d2.items():
        if key2 not in d1.keys() or value2 != d1[key2]:
            diff[key2] = value2
        elif isinstance(d1[key2], dict) and isinstance(value2, dict):
            diff[key2] = diff_dict(d1[key2], value2)
    return diff


def parse_scan_config(scan_config: dict) -> tuple:
    """
    parse the different entries of the dictionary to create
    the configuration that can be passed to the higher_order_scan function

    The function returns a tuple that contains some of the information that
    needs to be passed to the scan task
    """
    daq_label = scan_config['name']
    # check if any calibrations need to be performed before taking data
    calibration = None
    if 'calibration' in scan_config.keys():
        calibration = scan_config['calibration']

    # parse the scan dimensions
    scan_parameters = []
    if 'scan_parameters' not in scan_config.keys():
        raise ConfigFormatError("There needs to be a 'scan_parameters' list"
                                f" in the scan entry {daq_label}")
    for scan_dimension in scan_config['scan_parameters']:
        step = 1
        start = None
        stop = None
        if 'range' not in scan_dimension.keys():
            raise ConfigFormatError("A range must be specified"
                                    " for a scan dimension")
        for key, value in scan_dimension.items():
            if key == 'range':
                for subkey, subval in value.items():
                    if subkey == 'step':
                        step = subval
                    if subkey == 'start':
                        start = subval
                    if subkey == 'stop':
                        stop = subval
        if start is None or stop is None:
            raise ConfigFormatError(f"The Scan configuration {daq_label} is"
                                    " malformed. It misses either the start"
                                    " or stop entry for one of it's "
                                    " dimensions")
        scan_range = list(range(start, stop, step))
        scan_parameters.append((scan_dimension['key'], scan_range))
    return (scan_parameters, calibration, daq_label)


def parse_analysis_config(analysis_config: dict) -> tuple:
    """
    parse the analysis configuration from a dict and return it in the
    same way that the parse_scan_config

    Returns
        Tuple containing the parameters relevant to the analysis given
        by the analysis_label along with the name of the daq task that
        provides the data for the analysis
        analysis_parameters: parameters of the analysis to be performed
        daq: daq task required by the analysis
        analysis_label: name of the analysis
    """
    analysis_label = analysis_config['name']
    # parse the daq that is required for the analysis
    if 'daq' not in analysis_config.keys():
        raise ConfigFormatError("an analysis must specify a daq task")
    daq = analysis_config['daq']

    analysis_parameters = {}
    if 'parameters' in analysis_config.keys():
        if not isinstance(analysis_config['parameters'], dict):
            raise ConfigFormatError("The parameters of an analysis must be"
                                    " a dictionary")
        analysis_parameters = analysis_config['parameters']
    return (analysis_parameters, daq, analysis_label)


def parse_config_entry(entry: dict):
    """
    take care of calling the right function for the different configuration
    types calls the parse_scan_config and parse_analysis_config.
    """
    ptype = entry['type']
    if ptype.lower() == 'daq':
        return parse_scan_config(entry)
    if ptype.lower() == 'analysis':
        return parse_analysis_config(entry)
    raise ValueError("The type of a procedure must be"
                     " either daq or analysis")


def parse_config_file(config_path: str):
    path = Path(config_path)
    if not path.exists():
        raise ValueError("The filepath given does not exist")
    procedures = []
    workflows = []
    config = load_configuration(path)
    if isinstance(config, dict):
        if 'libraries' in config.keys():
            other_paths = config['libraries']
            for path in other_paths:
                other_procedures, other_workflows = parse_config_file(path)
                for procedure in other_procedures:
                    procedures.append(procedure)
                for workflow in other_workflows:
                    workflows.append(workflow)
        if 'workflows' in config.keys():
            pass
        if 'procedures' in config.keys():
            if isinstance(config['procedures'], list):
                for procedure in config['procedures']:
                    ptype = procedure['type']
                    if ptype.lower() == 'daq':
                        procedures.append(parse_scan_config(procedure))
                    elif ptype.lower() == 'analysis':
                        procedures.append(parse_analysis_config(procedure))
                    else:
                        raise ValueError("The type of a procedure must be"
                                         " either daq or analysis")
            else:
                raise ValueError("procedures must be a list, not a dictionary")
    elif isinstance(config, list):
        for entry in config:
            procedures.append(parse_config_entry(entry))
    return procedures, workflows


#### TESTS ####
def test_parse_scan_config():
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    scan_configs = []
    with open(test_fpath, 'r') as test_file:
        test_config = yaml.safe_load(test_file.read())
        for scan in test_config:
            scan_configs.append(parse_scan_config(scan))
    assert len(scan_configs[0][0][0][0]) == 3  # number of keys
    assert len(scan_configs) == 2  # number of different scans
    assert len(scan_configs[1][0]) == 2  # number of dimensions in the second scan
    assert scan_configs[0][0][0][0][0] == 'level1_key1'


def test_load_config():
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    config = load_configuration(test_fpath)
    assert isinstance(config, list)
    assert isinstance(config[0], dict)


def test_config_updater():
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    config = load_configuration(test_fpath)
    original = config[0]
    assert 'calibration' not in original
    update = {'calibration': 'pedestal_calibration'}
    updated_dict = update_dict(original, update)
    assert original['calibration'] == 'pedestal_calibration'


def test_patch_generator():
    keys = [['k1', 'k2', 'k3'], 'k4', 'k5']
    value = 1
    patch_dict = generate_patch_dict_from_key_tuple(keys, value)
    assert patch_dict['k1']['k4']['k5'] == 1
    assert patch_dict['k2']['k4']['k5'] == 1
    assert patch_dict['k3']['k4']['k5'] == 1


def test_diff_dict():
    test_dict_1 = {'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3}
    test_dict_2 = {'a': 2, 'b': {'c': 3, 'f': 4}, 'e': 3, 'g': 4}
    result = diff_dict(test_dict_1, test_dict_2)
    print(result)
    assert result['g'] == 4
    assert result['b']['c'] == 3
    assert result['a'] == 2
    result = diff_dict(test_dict_2, test_dict_1)
    assert result['b']['c'] == 2
    assert result['a'] == 1
