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
from typing import Union
from luigi.freezing import FrozenOrderedDict
import yaml
import jinja2


class ConfigPatchError(Exception):
    def __init__(self, message):
        self.message = message


class ConfigFormatError(Exception):
    def __init__(self, message):
        self.message = message


def load_configuration(config_path):
    """
    load the configuration dictionary from a yaml file

    :raises: ConfigFormatError if the input cannot be parsed by the yaml
    parser
    """
    with open(config_path, 'r', encoding='utf-8') as config_file:
        try:
            return yaml.safe_load(config_file.read())
        except yaml.YAMLError as e:
            raise ConfigFormatError("unable to load yaml") from e


def test_load_config():
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    config = load_configuration(test_fpath)
    assert isinstance(config, list)
    assert isinstance(config[0], dict)


def unfreeze(config):
    """
    unfreeze the dictionary that is frozen to serialize it
    and send it from one luigi task to another
    """
    try:
        unfrozen_dict = {}
        for key in config.keys():
            unfrozen_dict[key] = unfreeze(config[key])
        return unfrozen_dict
    except AttributeError:
        try:
            unfrozen_list = []
            if not isinstance(config, str):
                for elem in config:
                    unfrozen_list.append(unfreeze(elem))
                return unfrozen_list
            return config
        except TypeError:
            return config


def test_unfreeze():
    input_dict = FrozenOrderedDict({'a': 1, 'b': (1, 2, 3),
                                    'd': FrozenOrderedDict({'e': 4})})
    expected_dict = {'a': 1, 'b': [1, 2, 3],
                     'd': {'e': 4}}
    assert expected_dict == unfreeze(input_dict)


def update_dict(original: dict, update: dict, offset: bool = False,
                in_place: bool = False):
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
    Raises:
    TypeError: If offset is set to true and the types don't match the addition
               of the values will cause a TypeError to be raised

    ConfigPatchError: If lists are updated the length of the lists needs to
               match otherwise a error is raised
    """

    if in_place is True:
        result = original
    else:
        result = deepcopy(original)
    for update_key in update.keys():
        if update_key not in result.keys():
            if in_place is True:
                result[update_key] = update[update_key]
            else:
                result[update_key] = deepcopy(update[update_key])
            continue
        if not isinstance(result[update_key], type(update[update_key])):

            if in_place is True:
                result[update_key] = update[update_key]
            else:
                result[update_key] = deepcopy(update[update_key])
            continue
        if isinstance(result[update_key], dict):
            result[update_key] = update_dict(result[update_key],
                                             update[update_key],
                                             offset=offset,
                                             in_place=in_place)
        elif isinstance(result[update_key], list) or\
                isinstance(result[update_key], tuple):
            if len(result[update_key]) != len(update[update_key]):
                raise ConfigPatchError(
                    'If a list is a value of the dict the list'
                    ' lengths in the original and update need to'
                    ' match')
            patch = []
            for i, (orig_elem, update_elem) in enumerate(
                    zip(result[update_key], update[update_key])):
                if isinstance(orig_elem, dict):
                    patch.append(update_dict(result[update_key][i],
                                             update_elem,
                                             offset=offset,
                                             in_place=in_place))
                else:
                    if in_place is True:
                        patch.append(update_elem)
                    else:
                        patch.append(deepcopy(update_elem))
            if isinstance(result[update_key], tuple):
                patch = tuple(patch)
            result[update_key] = patch
        else:
            if offset is True:
                result[update_key] += update[update_key]
            else:
                if in_place is True:
                    result[update_key] = update[update_key]
                else:
                    result[update_key] = deepcopy(update[update_key])
    return result


def test_update_dict():
    """
    test the update_dict function
    """
    test_fpath = Path('../../examples/daq_procedures.yaml')
    config = load_configuration(test_fpath)
    original = config[0]
    assert 'calibration' in original
    assert original['calibration'] == 'pedestal_calibration'
    update = {'calibration': 'vref_no_inv'}
    updated_dict = update_dict(original, update)
    assert updated_dict['calibration'] == 'vref_no_inv'

    # check that subdicts are properly updated
    original = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'}
    update = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5]}
    expected_output = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5],
                       'that': 'what'}
    updated_dict = update_dict(original, update)
    assert updated_dict == expected_output

    # check that an update with an emty dict is a no-op
    original = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'}
    update = {}
    expected_output = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3],
                       'that': 'what'}
    updated_dict = update_dict(original, update)
    assert updated_dict == expected_output

    # check that the in_place feature works as expected
    original = {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'}
    update = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5]}
    expected_output = {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5],
                       'that': 'what'}
    update_dict(original, update, in_place=True)
    assert original == expected_output


def patch_configuration(config: dict, patch: dict):
    """
    currently only a wrapper function, if tests need to be implemented,
    then this is done here. Also the correct part of the cofiguration
    may be selected
    """
    return update_dict(config, patch)


def generate_patch(keys: Union[list, str], value):
    """
    Given a list of keys and a value generate a nested dict
    with one level of nesting for every entry in the list
    if any of the list entries is itself a list create a dict for every
    element of the list. Make s
    """
    # if the key is in fact a template for a yaml file
    if isinstance(keys, str):
        patch = yaml.safe_load(jinja2.Template(keys).render(value=value))
        if len(patch.keys()) != 1 and \
                (patch.keys()[0] != 'target' or patch.keys()[0] != 'daq'):
            patch = {'target': patch}
        return patch

    # this is needed to work with luigi as it turns stuffinto
    # tuples
    keys = list(keys)
    # here we need to insert 'target' if the key 'target' or 'daq' is not
    # present as the top level key to extend the scannable parameters to both
    # the daq and target configuration
    if keys[0] not in ['target', 'daq']:
        keys.insert(0, 'target')

    # now the rest of the generation can run as usual
    if len(keys) == 0:
        return {}
    keys.reverse()
    current_root = value
    for key in keys:
        level = {}
        if isinstance(key, list) or isinstance(key, tuple):
            for subkey in key:
                level[subkey] = deepcopy(current_root)
        else:
            level[key] = current_root
        current_root = level
    return current_root


def test_patch_generator():
    """
    test that the generate_patch_dict_from_key_tuple function
    """
    keys = [[['k1', 'k2', 'k3'], 'k4', 'k5'],
            ['daq', ['k1', 'k2', 'k3'], 'k4', 'k5'],
            ['daq', ['k1', 'k2', 'k3'], ['k4', 'k5'], 'k6']]
    value = 1
    expected_dict = [{'target': {'k1': {'k4': {'k5': 1}},
                                 'k2': {'k4': {'k5': 1}},
                                 'k3': {'k4': {'k5': 1}}}},
                     {'daq': {'k1': {'k4': {'k5': 1}},
                              'k2': {'k4': {'k5': 1}},
                              'k3': {'k4': {'k5': 1}}}},
                     {'daq': {'k1': {'k4': {'k6': 1},
                                     'k5': {'k6': 1}},
                              'k2': {'k4': {'k6': 1},
                                     'k5': {'k6': 1}},
                              'k3': {'k4': {'k6': 1},
                                     'k5': {'k6': 1}}
                              }
                      }]
    for key, exd_dict in zip(keys, expected_dict):
        patch_dict = generate_patch(key, value)
        assert patch_dict == exd_dict


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


def test_diff_dict():
    test_dict_1 = {'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3}
    test_dict_2 = {'a': 2, 'b': {'c': 3, 'f': 4}, 'e': 3, 'g': 4}
    diff = {'a': 2, 'b': {'c': 3}, 'g': 4}
    result = diff_dict(test_dict_1, test_dict_2)
    assert result == diff
    result = diff_dict(test_dict_2, test_dict_1)
    assert result['b']['c'] == 2
    assert result['a'] == 1


def parse_scan_dimension_values(scan_dimension):
    step = 1
    start = None
    stop = None
    if 'range' in scan_dimension and 'values' in scan_dimension:
        raise ConfigFormatError('range and values are mutually exclusive')
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
                raise ConfigFormatError(
                    "The Scan configuration is"
                    " malformed. It misses either the start"
                    " or stop entry for one of it's "
                    " dimensions")
            return list(range(start, stop, step))
        elif key == 'values':
            if not isinstance(value, list):
                raise ConfigFormatError(
                        "The Scan configuration is"
                        " malformed. The values key should contain "
                        "a list of values ")
            return value


def test_dimension_value_generation():
    daq_config = load_configuration(
        '../../tests/configuration/scan_procedures.yaml')
    scan_config = daq_config[0]
    scan_vals = parse_scan_dimension_values(scan_config['parameters'][0])
    assert len(scan_vals) == 2048
    for i, val in enumerate(scan_vals):
        assert i == val


def build_scan_dim_patch_set(scan_dimension):
    scan_values = parse_scan_dimension_values(scan_dimension)
    patch_set = []
    try:
        if scan_dimension['key'] is None:
            return [{}]
        scan_dim_key = scan_dimension['key']
        for val in scan_values:
            patch = generate_patch(scan_dim_key, val)
            patch_set.append(patch)
        return patch_set
    except KeyError:
        try:
            template = scan_dimension['template']
            template = jinja2.Template(template)
            for val in scan_values:
                patch_set.append(yaml.safe_load(template.render(value=val)))
            return patch_set
        except jinja2.TemplateSyntaxError as e:
            raise ConfigFormatError(
                    f"The template is malformed: {e.message}")
        except KeyError:
            raise ConfigFormatError(
                    "Neither the template keyword nor the 'key' keyword"
                    " could not be found")


def test_build_patch_set():
    daq_config = load_configuration(
        '../../tests/configuration/scan_procedures.yaml')
    scan_dimension = daq_config[0]['parameters'][0]
    scan_parameters = build_scan_dim_patch_set(scan_dimension)
    assert len(scan_parameters) == 2048
    for patch in scan_parameters:
        assert isinstance(patch, dict)

    scan_dimension = daq_config[1]['parameters'][0]
    scan_parameters = build_scan_dim_patch_set(scan_dimension)
    assert len(scan_parameters) == 35
    for patch in scan_parameters:
        assert isinstance(patch, dict)
    assert scan_parameters[0]['target']['roc_s0']['ch'][1]['HighRange'] == 1


def parse_scan_parameters(scan_config: dict):
    scan_parameters = []
    try:
        for scan_dimension in scan_config['parameters']:
            scan_parameters.append(build_scan_dim_patch_set(scan_dimension))
        scan_config['parameters'] = scan_parameters
    except KeyError:
        scan_config['parameters'] = None
    return scan_parameters


def test_parse_scan_parameters():
    daq_config = load_configuration(
        '../../tests/configuration/scan_procedures.yaml')
    scan_config = daq_config[0]
    scan_parameters = parse_scan_parameters(scan_config)
    assert len(scan_parameters) == 1
    assert len(scan_parameters[0]) == 2048
    for patch in scan_parameters[0]:
        assert isinstance(patch, dict)


def parse_daq_parameters(scan_config: dict, path: Path):
    try:
        if not isinstance(scan_config['parameters'], list):
            raise ConfigFormatError(
                f"The parameters section of daq {scan_config['name']} in"
                f" file {path.resolve()} needs to be a list")
    except KeyError:
        scan_config['parameters'] = []
        return
    for scan_dimension in scan_config['parameters']:
        if ('key' not in scan_dimension and 'template' not in scan_dimension)\
           or (('range' not in scan_dimension)
               and ('values' not in scan_dimension)):
            raise ConfigFormatError(
                    "A range or a list of values along with "
                    "a key must be specified"
                    f" for a scan dimension daq config {scan_config['name']}"
                    f" in file {path.resolve()}")
        if 'key' in scan_dimension and 'template' in scan_dimension:
            raise ConfigFormatError(
                "'key' and 'template' are mutually"
                f" exclusive, both where defined in {scan_config['name']} in"
                f" file {path.resolve()}")
        if 'key' in scan_dimension:
            if not isinstance(scan_dimension['key'], list):
                raise ConfigFormatError(
                    "The key field in the parameter section of "
                    " needs to be a list")
        if 'template' in scan_dimension:
            template = scan_dimension['template']
            try:
                template = jinja2.Template(template)
            except jinja2.TemplateSyntaxError as e:
                raise ConfigFormatError(
                    "The template in"
                    f" scan config {scan_config['name']} in "
                    f"file {path.resolve()} is malformed") from e
        scan_dimension['values'] = parse_scan_dimension_values(scan_dimension)
        if 'range' in scan_dimension:
            del scan_dimension['range']
    scan_config['parameters'].sort(key=lambda x: len(x['values']))


def parse_system_settings(system_settings: dict, name: str, path: str) -> dict:
    """
    Parses the system settings section of a daq configuration

    Parameters
    ---------
    system_settings : dict
        the subsection of the config that is labled system_settings
    name : str
        the name of the daq procedure being parsed
    path : Path
        the path to the file the current daq procedure is defined in

    Raises
    ------
    ConfigFormatError :
        if an error in the format is detected, this kind of error is raised
        directly by the function.
    """
    path = Path(path)
    dir = Path(os.path.dirname(path))
    try:
        default_path = system_settings['default']
    except KeyError:
        raise ConfigFormatError(
            f'No default config specified in procedure {name} in file'
            f' {path.resolve()}')
    if not isinstance(default_path, list):
        default_path = [default_path]
    full_paths = []
    for rel_path in default_path:
        rel_path = Path(rel_path)
        full_path = dir / rel_path
        if not full_path.exists():
            raise ConfigFormatError(
                f"the default config file {full_path} can't be found")
        full_paths.append(full_path.resolve())
    system_settings['default'] = full_paths

    try:
        init_paths = system_settings['init']
    except KeyError:
        raise ConfigFormatError(
            f'No init config specified in procedure {name} in file'
            f' {path.resolve()}')
    if not isinstance(init_paths, list):
        init_paths = [init_paths]
    full_paths = []
    for rel_path in init_paths:
        rel_path = Path(rel_path)
        full_path = dir / rel_path
        if not full_path.exists():
            raise ConfigFormatError(
                f"the init config file {full_path} can't be found")
        full_paths.append(full_path.resolve())
    system_settings['init'] = full_paths

    try:
        if not isinstance(system_settings['override'], dict):
            raise ConfigFormatError(
                f'the override section in procedure {name} in file '
                f'{path.resolve()} needs to be a dictionary')
    except KeyError:
        system_settings['override'] = {}


def parse_daq_config(daq_config: dict, path: str):
    """
    parse the different entries of the dictionary to create
    the configuration that can be passed to the higher_order_scan function

    The function returns a tuple that contains some of the information that
    needs to be passed to the scan task

    The scan configuration allows it to override the parameters of a default
    daq-system configuration with ones specified in the sever_override and
    client_override section

    Parameters
    ---------
    daq_config : dict
        Dictionary that is the configuration for a single scan/measurement
    path : str
        Path to the file that contained the scan_config dict in yaml
        format this is needed to be able to find the daq-system default
        configuration

    Returns
    -------
    This funciton does not return anything directly instead altering the
    contents of the daq_config dict
    """
    # get the directory the file is located in
    scan_config_path = Path(path)
    try:
        if not isinstance(daq_config['name'], str):
            ConfigFormatError(f'A procedure inside the file'
                              f' {scan_config_path.resolve()} has an'
                              ' invalid `name`')
    except KeyError:
        raise ConfigFormatError(f'A daq procedure in {path} has no name')

    # the verification of type is skipped because this is done in the
    # previous function

    # check if any calibrations need to be performed before taking data
    try:
        if not isinstance(daq_config['calibration'], str):
            raise ConfigFormatError(
                    'The calibration needs to be the '
                    'name of the procedure used to calibrate '
                    'the current procedure')
    except KeyError:
        daq_config['calibration'] = None

    try:
        if not isinstance(daq_config['merge'], bool):
            raise ConfigFormatError("The merge_data field of procedure"
                                    f" {daq_config['name']} in file "
                                    f"{scan_config_path.resolve()}"
                                    " needs to be a bool")
    except KeyError:
        daq_config['merge'] = False

    try:
        if 'summary' != daq_config['mode'] and 'full' != daq_config['mode']:
            raise ConfigFormatError(f'The mode specified in procedure '
                                    f'{daq_config["name"]} in file '
                                    f'{scan_config_path.resolve()} is not '
                                    f'"full" or "summary"')
    except KeyError:
        daq_config['mode'] = 'summary'

    try:
        if not isinstance(daq_config['data_columns'], list):
            raise ConfigFormatError("The columns key must be a list of the "
                                    " dataframe, columns is a "
                                    f"{type(daq_config['data_columns'])}")
    except KeyError:
        daq_config['data_columns'] = 'all'

    try:
        system_settings = daq_config['system_settings']
    except KeyError:
        raise ConfigFormatError(
            f'the procedure {daq_config["name"]} in file {path.resolve()}'
            ' needs a system_settings entry')
    parse_system_settings(system_settings, daq_config['name'], path)
    parse_daq_parameters(daq_config, path)


def test_parse_scan_config():
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    test_dir = Path(os.path.dirname(test_fpath))
    test_configs = load_configuration(test_fpath)
    for i, scan in enumerate(test_configs):
        parse_daq_config(test_configs[i], test_fpath)

    # test with the first daq_procedure
    test_config = test_configs[0]
    assert test_config['name'] == 'timewalk_scan'
    assert test_config['type'] == 'daq'
    assert isinstance(test_config['system_settings']['default'], list)
    assert len(test_config['system_settings']['default']) == 2
    assert isinstance(test_config['system_settings']['init'], list)
    assert len(test_config['system_settings']['init']) == 1
    init_path = test_dir / 'init_timewalk_scan.yaml'
    daq_path = test_dir / 'defaults/daq-system-config.yaml'

    assert test_config['system_settings']['init'][0].resolve()\
        == init_path.resolve()
    assert test_config['system_settings']['default'][1].resolve()\
        == daq_path.resolve()
    assert test_config[
        'system_settings']['override']['daq']['server']['NEvents'] == 1000
    assert test_config['system_settings']['override'][
            'daq']['server']['l1a_generator_settings'][0]['BX'] == 16
    assert len(test_config['parameters']) == 1
    assert 'key' in test_config['parameters'][0]
    assert 'values' in test_config['parameters'][0]
    test_config = test_configs[0]
    tree_dim = [len(dim['values']) for dim in test_config['parameters']]
    for td, ptd in zip(tree_dim[1:], tree_dim[:-1]):
        assert td >= ptd


def parse_analysis_config(config: dict, path: str) -> tuple:
    """
    parse the analysis configuration from a dict and return it in the
    same way that the parse_scan_config

    Returns
    -------
    Tuple containing the parameters relevant to the analysis given
    by the analysis_label along with the name of the daq task that
    provides the data for the analysis
    analysis_parameters: parameters of the analysis to be performed
    daq: daq task required by the analysis
    analysis_label: name of the analysis
    """
    path = Path(path)
    try:
        if not isinstance(config['name'], str):
            ConfigFormatError(f'A procedure inside the file'
                              f' {path.resolve()} has an'
                              ' invalid `name`')
    except KeyError:
        raise ConfigFormatError(
                f'An analysis procedure in {path.resolve()} has no name')

    try:
        if not isinstance(config['module_name'], str):
            raise ConfigFormatError(
                    f"The 'module_name' field of the analysis {config['name']}"
                    f" needs to contain a string")
    except KeyError:
        config['module_name'] = config['name']

    # parse the daq that is required for the analysis
    try:
        if not isinstance(config['daq'], str):
            raise ConfigFormatError(
                    f"The 'daq' field of the analysis {config['name']}"
                    f" in file {path.resolve()} needs to contain a string")
    except KeyError:
        raise ConfigFormatError(
                f"The analysis {config['name']} in file {path.resolve()} "
                "must specify a daq task")

    try:
        if not isinstance(config['parameters'], dict):
            raise ConfigFormatError(
                    f"The parameters section of analysis {config['name']}"
                    f" in file {path.resolve()} needs to be a dictionary")
    except KeyError:
        config['parameters'] = None


def test_analysis_config():
    test_fpath = Path('../../examples/analysis_procedures.yaml')
    config = load_configuration(test_fpath)
    parse_analysis_config(config[0], test_fpath)
    parsed_config = config[0]
    assert parsed_config['daq'] == 'example_scan'
    assert isinstance(parsed_config['parameters'], dict)
    assert parsed_config['name'] == 'example_analysis'
    assert parsed_config['type'] == 'analysis'
    assert not parsed_config['event_mode']
    ana_params = parsed_config['parameters']
    assert ana_params['p1'] == 346045
    assert ana_params['p2'] == 45346
    assert ana_params['p3'] == 'string option'


def parse_config_entry(entry: dict, path: str):
    """
    take care of calling the right function for the different configuration
    types calls the parse_scan_config and parse_analysis_config.
    """
    try:
        ptype = entry['type']
    except KeyError:
        ConfigFormatError(
                f"A procedure configuration was found in {path} that"
                " does not define a type")
    if ptype.lower() == 'daq':
        parse_daq_config(entry, path)
    elif ptype.lower() == 'analysis':
        parse_analysis_config(entry)
    else:
        raise ValueError("The type of a procedure must be"
                         " either daq or analysis")


def test_parse_config_entry():
    scan_test_config = Path('../../tests/configuration/scan_procedures.yaml')
    config = load_configuration(scan_test_config)
    for i in range(len(config)):
        parse_config_entry(config[i], scan_test_config)
    names = ['timewalk_scan', 'timewalk_scan_with_template',
             'timewalk_scan_v2',
             'timewalk_and_phase_scan', 'full_toa_scan',
             'master_tdc_SIG_calibration_daq',
             'master_tdc_REF_calibration_daq']
    for name, entry in zip(names, config):
        assert name == entry['name']


def validate_wokflow_config(wflows, config_path):
    validated = []
    if not isinstance(wflows, list):
        raise ValueError(f"The workflows field in {config_path} "
                         "must be a list")
    for wf in wflows:
        if not isinstance(wf, dict):
            raise ValueError(f"A workflow in {config_path} is malformed")
        if 'name' not in wf:
            raise ValueError(f"A workflow in {config_path} is malformed")
        if 'tasks' not in wf:
            raise ValueError(f"The workflow {wf['name']} in "
                             f"{config_path} needs a name attribute")
        validated.append(wf)
    return validated


def parse_config_file(config_path: str):
    """
    Parse the root config file and return a list of workflows and
    procedures that are fully parsed so that with them the analyses
    and scan can be properly initialized
    """
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError("The filepath %s given does not exist" % path)
    procedures = []
    workflows = []
    config = load_configuration(path)
    if isinstance(config, dict):
        if 'libraries' in config.keys():
            # resolve the path to the library files taking
            # into account that both relative and absolute
            # paths can be specified in the libraries
            # section
            lib_root_dir = Path(os.path.dirname(path))
            other_paths = config['libraries']
            for lib_path in other_paths:
                if not str(lib_path).startswith('/'):
                    resolved_lib_path = lib_root_dir / lib_path
                else:
                    resolved_lib_path = Path(lib_path).resolve()
                other_procedures, other_workflows = parse_config_file(
                        resolved_lib_path)
                procedures = procedures + other_procedures
                workflows = workflows + other_workflows
        if 'workflows' in config.keys():
            raw_workflows = config['workflows']
            workflows = workflows + validate_wokflow_config(raw_workflows,
                                                            path)
        # The root configuration file can also specify new
        # procedures, similar to libraries
        if 'procedures' in config.keys():
            if isinstance(config['procedures'], list):
                for procedure in config['procedures']:
                    ptype = procedure['type']
                    if ptype.lower() == 'daq':
                        procedures.append(parse_daq_config(procedure, path))
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


def test_parse_config_file():
    config_file = Path('../../tests/configuration/main_config.yaml')
    procedures, workflows = parse_config_file(config_file)
    assert procedures is not None
    assert len(procedures) == 7
    assert len(workflows) == 1


def get_system_config(procedure_config: dict):
    config = {}
    init_config_fragments = [
            load_configuration(icp)
            for icp in procedure_config['system_settings']['init']]
    for frag in init_config_fragments:
        update_dict(config, frag, in_place=True)
    override = procedure_config['system_settings']['override']
    update_dict(config, override, in_place=True)
    return config


def get_system_default_config(procedure_config: dict):
    config = {}
    default_config_fragments = [
            load_configuration(dcp)
            for dcp in procedure_config['system_settings']['default']]
    for frag in default_config_fragments:
        update_dict(config, frag, in_place=True)
    return config


def test_get_system_config():
    test_configs = _get_daq_configs()
    test_config = test_configs[0]
    default_daq_config = load_configuration(
            test_config['system_settings']['default'][1])['daq']
    system_default_config = get_system_default_config(test_config)['daq']
    print(system_default_config)
    delta = diff_dict(default_daq_config, system_default_config)
    assert delta is None


def generate_worker_config(system_state: dict):
    """
    create procedure configrurations that can be distributed to the worker
    tasks.

    Do this by figuring out how many runs there are and how many workers there
    and then modifying the parameters section of the procedure configuration
    for each worker so that the worker will work through roughly 1/nworker
    of the runs
    """
    values = [parse_scan_dimension_values(dim)
              for dim in system_state['procedure']['parameters']]
    total_runs = 1
    tree_dim = [1]
    for val in values:
        total_runs *= len(val)
        assert len(val) > tree_dim[-1]
        tree_dim.append(len(val))

    workers = system_state['workers']

    split_level = len(tree_dim) - 1
    for i, dim in enumerate(tree_dim):
        if dim >= workers:
            split_level = i - 1
            break
    split_vals = [values[split_level][i::workers] for i in range(workers)]

    worker_states = []
    for vals in split_vals:
        worker_state = deepcopy(system_state)
        worker_state['procedure']['parameters'][split_level]['values'] = vals
        worker_states.append(worker_state)
    return worker_states


def test_generate_subsystem_states():
    scan_configs = _get_daq_configs()
    test_config = scan_configs[0]
    reference_dim = [len(dim['values'])
                     for dim in test_config['parameters']]
    system_state = {}
    system_state['workers'] = 1
    system_state['procedure'] = test_config
    for state in generate_worker_config(system_state):
        parameters = state['procedure']['parameters']
        tree_dim = [len(dim['values']) for dim in parameters]
        assert tree_dim == reference_dim
    system_state = {}
    system_state['workers'] = 3
    system_state['procedure'] = test_config
    for i, state in enumerate(generate_worker_config(system_state)):
        parameters = state['procedure']['parameters']
        tree_dim = [len(dim['values']) for dim in parameters]
        assert len(tree_dim) == len(reference_dim)
        assert parameters[0]['values'] == list(range(2048))[i::3]

    test_config = scan_configs[3]
    system_state = {}
    system_state['workers'] = 3
    system_state['procedure'] = test_config
    dim_vals = [dim['values']
                for dim in system_state['procedure']['parameters']]
    ref_tree_dim = [len(vals) for vals in dim_vals]
    assert system_state['procedure']['name'] == 'timewalk_and_phase_scan'
    collected_dim_vals = [[] for vals in dim_vals]
    merge_dim = 0
    for i, state in enumerate(generate_worker_config(system_state)):
        parameters = state['procedure']['parameters']
        tree_dim = [len(dim['values']) for dim in parameters]
        for j, dim in enumerate(parameters):
            if tree_dim[j] != ref_tree_dim[j]:
                merge_dim = j
                collected_dim_vals[j] += dim['values']
    assert len(collected_dim_vals[merge_dim]) == len(dim_vals[merge_dim])
    for val in collected_dim_vals[merge_dim]:
        assert val in dim_vals[merge_dim]


def _get_daq_configs():
    """
    Function that makes loading scan configurations a one liner
    instead of copying the code everywhere
    """
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    # test_dir = Path(os.path.dirname(test_fpath))
    test_config = load_configuration(test_fpath)
    for i, _ in enumerate(test_config):
        parse_daq_config(test_config[i], test_fpath)
    return test_config
