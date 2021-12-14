"""
Module containing the utilities to parse and properly prepare the configuration
provided by the user

The functions here are testable by calling pytest config_utilities.py
The tests can also be used as a guide on how to use the functions and
what to expect of their behaviour
"""
from pathlib import Path
import os
from copy import deepcopy
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
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return yaml.safe_load(config_file.read())


def update_dict(original: dict, update: dict, offset: bool = False):
    """
    update one multi level dictionary with another. If a key does not
    exist in the original, it is created. the updated dictionary is returned

    Arguments:
    original: the unaltered dictionary

    update: the dictionary that will either overwrite or extend the original

    offset: If True, the values in the update dictionary will be interpreted as
            offsets to the values in the original dict. The resulting value wil
            be original + update (this will be string concatenation if both the
            original and update values are strings

    Returns:
    updated_dict: the extended/updated dict where the values that do not appear
                  in the update dict are from the original dict, the keys that
                  do appear in the update dict overwrite/extend the values in
                  the original
    """
    result = deepcopy(original)
    for update_key in update.keys():
        if update_key in result.keys():
            if not isinstance(update[update_key], type(result[update_key])):
                raise ConfigPatchError(
                        'The type of the patch does not match the '
                        'type of the original value')
            if isinstance(result[update_key], dict):
                result[update_key] = update_dict(result[update_key],
                                                 update[update_key])
            elif isinstance(result[update_key], list):
                if len(result[update_key]) != len(update[update_key]):
                    raise ConfigPatchError(
                            'If a list is a value of the dict the list'
                            ' lengths in the original and update need to'
                            ' match')
                for i, (orig_elem, update_elem) in enumerate(
                        zip(result[update_key], update[update_key])):
                    if not isinstance(update_elem, type(orig_elem)):
                        raise ConfigPatchError(
                                'The type of the patch does not match the '
                                'type of the original value')
                    if isinstance(orig_elem, dict):
                        result[update_key][i] = update_dict(orig_elem,
                                                            update_elem)
                    else:
                        result[update_key][i] = update_elem
            else:
                if offset is True:
                    result[update_key] += update[update_key]
                else:
                    result[update_key] = update[update_key]
        else:
            result[update_key] = update[update_key]
    return result


def patch_configuration(config: dict, patch: dict):
    """
    currently only a wrapper function, if tests need to be implemented,
    then this is done here. Also the correct part of the cofiguration
    may be selected
    """
    return update_dict(config, patch)


def generate_patch(keys: list, value):
    """
    the Scan task receives a list of keys and values and needs
    to generate a patch from one of the values of the list
    and all the keys. This function does that
    """
    keys.reverse()
    current_root = value
    for key in keys:
        level = {}
        if isinstance(key, list):
            for subkey in key:
                level[subkey] = deepcopy(current_root)
        else:
            level[key] = current_root
        current_root = level
    return current_root


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
        if key2 not in d1.keys():
            diff[key2] = value2
        elif isinstance(d1[key2], dict) and isinstance(value2, dict):
            potential_diff = diff_dict(d1[key2], value2)
            if potential_diff is not None:
                diff[key2] = potential_diff
        elif value2 != d1[key2]:
            diff[key2] = value2
    if diff == {}:
        return None
    return diff


def parse_scan_config(scan_config: dict, path: str) -> tuple:
    """
    parse the different entries of the dictionary to create
    the configuration that can be passed to the higher_order_scan function

    The function returns a tuple that contains some of the information that
    needs to be passed to the scan task

    The scan configuration allows it to override the parameters of a default
    daq-system configuration with ones specified in the sever_override and
    client_override section

    Arguments:
        scan_config: Dictionary that is the configuration for a single
                     scan/measurement
        path: Path to the file that contained the scan_config dict in yaml
              format this is needed to be able to find the daq-system default
              configuration
    Returns:
        the tuple of scan parameters, scan_requirement, scan_name and
        daq_system configuration.
    """
    daq_label = scan_config['name']
    scan_config_path = Path(path)
    scan_file_dir = os.path.dirname(scan_config_path)

    # check if any calibrations need to be performed before taking data
    calibration = None
    if 'calibration' in scan_config.keys():
        calibration = scan_config['calibration']

    # parse the daq-system configuration
    if 'daq_settings' not in scan_config.keys():
        raise ConfigFormatError("A daq Task must specify a 'daq_settings'"
                                " section that at least contains the path"
                                " to the default system config used")
    if 'default' not in scan_config['daq_settings']:
        raise ConfigFormatError("A daq Task must provide the full daq-system"
                                " configuration via a link to a default file"
                                " with the 'default' entry in the yaml file")
    # build the path for the default config
    default_daq_settings_path = scan_file_dir / \
        Path(scan_config['daq_settings']['default'])
    # load the default config
    if not default_daq_settings_path.is_file():
        raise ConfigFormatError(f"The path specified for the default config"
                                f"of the daq_settings in {daq_label} does"
                                " not exist")
    default_daq_config = load_configuration(default_daq_settings_path)

    # apply the override parameters for the server and the client
    patched_daq_system_config = default_daq_config.copy()
    for override_prefix in ['server', 'client']:
        override_key = override_prefix+'_override'
        if override_key in scan_config['daq_settings'] and \
                isinstance(scan_config['daq_settings'][override_key], dict):
            override_config = scan_config['daq_settings'][override_key]
            override_config = {override_prefix: override_config}
            patched_daq_system_config = update_dict(patched_daq_system_config,
                                                    override_config)
        # if the override entry is empty then don't do anything
        elif override_key in scan_config['daq_settings'] and \
                scan_config['daq_settings'][override_key] is None:
            pass
        else:
            raise ConfigFormatError(f"The {override_key} section in the daq"
                                    f"task {daq_label} must be a yaml dict")

    # parse the scan dimensions
    scan_parameters = []
    if 'parameters' not in scan_config.keys():
        raise ConfigFormatError("There needs to be a 'parameters' list"
                                f" in the scan entry {daq_label}")
    for scan_dimension in scan_config['parameters']:
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
    return (scan_parameters, calibration, daq_label, patched_daq_system_config)


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


def parse_config_entry(entry: dict, path: str):
    """
    take care of calling the right function for the different configuration
    types calls the parse_scan_config and parse_analysis_config.
    """
    ptype = entry['type']
    if ptype.lower() == 'daq':
        return parse_scan_config(entry, path)
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
                        procedures.append(parse_scan_config(procedure, path))
                    elif ptype.lower() == 'analysis':
                        procedures.append(parse_analysis_config(procedure))
                    else:
                        raise ValueError("The type of a procedure must be"
                                         " either daq or analysis")
            else:
                raise ValueError("procedures must be a list, not a dictionary")
    elif isinstance(config, list):
        for entry in config:
            procedures.append(parse_config_entry(entry, path))
    return procedures, workflows


#### TESTS ####
def test_load_config():
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    config = load_configuration(test_fpath)
    assert isinstance(config, list)
    assert isinstance(config[0], dict)


def test_update_dict():
    """
    test the update_dict function
    """
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    config = load_configuration(test_fpath)
    original = config[0]
    assert 'calibration' in original
    assert original['calibration'] == 'pedestal_calibration'
    update = {'calibration': 'vref_no_inv'}
    updated_dict = update_dict(original, update)
    assert updated_dict['calibration'] == 'vref_no_inv'
    original = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'}
    update = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5]}
    expected_output = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5],
                       'that': 'what'}
    updated_dict = update_dict(original, update)
    assert updated_dict == expected_output
    original = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'}
    update = {}
    expected_output = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3],
                       'that': 'what'}
    updated_dict = update_dict(original, update)
    assert updated_dict == expected_output


def test_patch_generator():
    """
    test that the generate_patch_dict_from_key_tuple function
    """
    keys = [['k1', 'k2', 'k3'], 'k4', 'k5']
    value = 1
    expected_dict = {'k1': {'k4': {'k5': 1}},
                     'k2': {'k4': {'k5': 1}},
                     'k3': {'k4': {'k5': 1}}}
    patch_dict = generate_patch(keys, value)
    assert patch_dict == expected_dict


def test_diff_dict():
    test_dict_1 = {'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3}
    test_dict_2 = {'a': 2, 'b': {'c': 3, 'f': 4}, 'e': 3, 'g': 4}
    diff = {'a': 2, 'b': {'c':3}, 'g': 4}
    result = diff_dict(test_dict_1, test_dict_2)
    assert result == diff
    result = diff_dict(test_dict_2, test_dict_1)
    assert result['b']['c'] == 2
    assert result['a'] == 1


def test_parse_scan_config():
    test_fpath = Path('./test_configurations/scan_procedures.yaml')
    scan_configs = []
    test_config = load_configuration(test_fpath)
    for scan in test_config:
        scan_configs.append(parse_scan_config(scan, test_fpath))
    assert len(scan_configs[0][0][0][0]) == 3  # number of keys
    assert len(scan_configs) == 3  # number of different scans
    assert len(scan_configs[1][0]) == 2  # number of dimensions in the second scan
    assert scan_configs[0][0][0][0][0] == 'level1_key1'


def test_analysis_config():
    test_fpath = Path('./test_configurations/analysis_procedures.yaml')
    config = load_configuration(test_fpath)
    ana_params, ana_daq, ana_label = parse_analysis_config(config[0])
    assert ana_daq == 'pedestal_scan'
    assert 'p1' in ana_params.keys()
    assert 'p2' in ana_params.keys()
    assert 'p3' in ana_params.keys()
    assert ana_label == 'pedestal_calibration'
    assert ana_params['p1'] == 346045
    assert ana_params['p2'] == 45346
    assert ana_params['p3'] == 'string option'


def test_parse_config_entry():
    scan_test_config = Path('./test_configurations/scan_procedures.yaml')
    daq_system_test_config = Path('./default_configs/daq-system-config.yaml')
    daq_reference_config = load_configuration(daq_system_test_config)
    config = load_configuration(scan_test_config)
    names = ['injection_scan', 'timewalk_scan', 'pedestal_scan']
    lengths = [1, 2, 1]
    expected_diffs = [{'server': {'NEvents': '4000'}, 'client': {'hw_type': 'HD'}},
                      {'server': {'port': 7777, 'IdelayStep': '3'},
                       'client': {'server_port': 7777}},
                      None]
    for entry, name, length, daq_diff in \
            zip(config, names, lengths, expected_diffs):
        params, requirement, cfg_name, daq_system_config = parse_config_entry(
                entry, scan_test_config)
        assert cfg_name == name
        assert len(params) == length
        assert daq_diff == diff_dict(daq_reference_config, daq_system_config)
