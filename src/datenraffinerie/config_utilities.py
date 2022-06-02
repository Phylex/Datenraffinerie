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
    if ('key' not in scan_dimension and 'template' not in scan_dimension)\
       or (('range' not in scan_dimension)
           and ('values' not in scan_dimension)):
        raise ConfigFormatError("A range or a list of values along with "
                                "a key must be specified"
                                " for a scan dimension")
    if 'key' in scan_dimension and 'template' in scan_dimension:
        raise ConfigFormatError("'key' and 'template' are mutually"
                                " exclusive")
    if 'key' in scan_dimension:
        if scan_dimension['key'] is None:
            return [{}]
        scan_dim_key = scan_dimension['key']
        if not isinstance(scan_dim_key, list):
            raise ConfigFormatError(
                    "The key field in the parameter section of "
                    " needs to be a list")
        for val in scan_values:
            patch = generate_patch(scan_dim_key, val)
            patch_set.append(patch)
        return patch_set
    if 'template' in scan_dimension:
        template = scan_dimension['template']
        try:
            template = jinja2.Template(template)
        except jinja2.TemplateSyntaxError as e:
            raise ConfigFormatError(
                    "The template in"
                    " scan config {daq_label} is malformed") from e
        for val in scan_values:
            patch_set.append(yaml.safe_load(template.render(value=val)))
        return patch_set


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
    # parse the scan dimensions
    daq_label = scan_config['name']
    scan_parameters = []
    if 'parameters' not in scan_config:
        raise ConfigFormatError("There needs to be a 'parameters' list"
                                f" in the scan entry {daq_label}")
    for scan_dimension in scan_config['parameters']:
        scan_parameters.append(build_scan_dim_patch_set(scan_dimension))
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
    scan_file_dir = Path(os.path.dirname(scan_config_path))

    # check if any calibrations need to be performed before taking data
    if 'calibration' not in scan_config:
        scan_config['calibration'] = None
    elif not isinstance(scan_config['calibration'], str):
        raise ConfigFormatError(
                'The calibration needs to be the '
                'name of the procedure used to calibrate '
                'the current procedure')

    try:
        raw_data = scan_config['event_mode']
        if not isinstance(raw_data, bool):
            raise ConfigFormatError("The event_data field needs to contain a"
                                    " boolean")
    except KeyError:
        scan_config['event_mode'] = False
    # parse the daq-system configuration
    # build the path for the default config
    try:
        daq_settings = scan_config['daq_settings']
    except KeyError as err:
        raise ConfigFormatError("A daq Task must specify a 'daq_settings'"
                                " section that at least contains the "
                                "'default' key pointing"
                                " to the default system config used") from err
    try:
        default_daq_settings_path = scan_file_dir / \
            Path(daq_settings['default'])
    except KeyError as err:
        raise ConfigFormatError("A daq Task must specify a 'daq_settings'"
                                " section that at least contains the "
                                "'default' key pointing"
                                " to the default system config used") from err
    # load the default config
    try:
        daq_system_config = load_configuration(
                default_daq_settings_path.resolve())
        daq_system_default_config = daq_system_config
        scan_config['daq_settings']['default'] = daq_system_default_config
    except FileNotFoundError as err:
        raise ConfigFormatError(f"The path specified for the default config"
                                f"of the daq_settings in {daq_label} does"
                                " not exist") from err
    if 'server_override' not in scan_config['daq_settings']:
        scan_config['daq_settings']['server_override'] = {}
    if 'client_override' not in scan_config['daq_settings']:
        scan_config['daq_settings']['client_override'] = {}

    # load the power on and initial config for the target
    try:
        target_config = scan_config['target_settings']
    except KeyError as err:
        raise ConfigFormatError(f"The 'target_settings' section in the daq"
                                f" task {daq_label} is missing") from err
    try:
        target_power_on_config_path = target_config['power_on_default']
    except KeyError as err:
        raise ConfigFormatError(f"The 'power_on_default' key in the daq"
                                f" task {daq_label} is missing. It should"
                                "be a path to the power on default config"
                                " of the target") from err
    try:
        pwr_on_path = scan_file_dir /\
                target_power_on_config_path
        target_power_on_config = load_configuration(pwr_on_path)
        scan_config['target_settings']['power_on_default']\
            = target_power_on_config
    except FileNotFoundError as err:
        raise ConfigFormatError(f"The target power on configuration for"
                                f" {daq_label} could not be found") from err
    try:
        initial_config_path = target_config['initial_config']
    except KeyError as err:
        raise ConfigFormatError(f"The 'initial_config' key in the daq"
                                f" task {daq_label} is missing. It should"
                                "be a path to the configuration of the "
                                " target at the beginning of the measure"
                                "ments") from err
    try:
        init_cfg_path = scan_file_dir / initial_config_path
        target_initial_config = load_configuration(init_cfg_path.resolve())
        scan_config['target_settings']['initial_config']\
            = target_initial_config
    except FileNotFoundError as err:
        raise ConfigFormatError(f"The initial target config of {daq_label}"
                                " could not be found") from err

    try:
        if not isinstance(scan_config['data_columns'], list):
            raise ConfigFormatError("The columns key must be a list of the "
                                    " dataframe, columns is a "
                                    f"{type(scan_config['data_columns'])}")
    except KeyError:
        scan_config['data_columns'] = None
    scan_parameters = parse_scan_parameters(scan_config)
    scan_config['parameters'] = scan_parameters
    return scan_config


def test_parse_scan_config():
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    test_dir = Path(os.path.dirname(test_fpath))
    scan_configs = []
    test_config = load_configuration(test_fpath)
    for scan in test_config:
        scan_configs.append(parse_scan_config(scan, test_fpath))
    assert len(scan_configs) == 7  # number of different scans

    # test with the first daq_procedure
    test_config = scan_configs[0]
    assert test_config['name'] == 'timewalk_scan'
    assert test_config['type'] == 'daq'
    assert isinstance(test_config['target_settings']['power_on_default'], dict)
    assert len(test_config['target_settings']['power_on_default']) == 3
    assert isinstance(test_config['target_settings']['initial_config'], dict)
    assert len(test_config['target_settings']['initial_config']) == 3
    init_config = load_configuration(test_dir
                                     / 'init_timewalk_scan.yaml')
    assert test_config['target_settings']['initial_config'] == init_config
    daq_config = load_configuration(test_dir /
                                    'defaults/daq-system-config.yaml')
    assert test_config['daq_settings']['default'] == daq_config
    assert test_config['daq_settings']['client_override'] == {}
    assert test_config['daq_settings']['server_override']['NEvents'] == 1000
    assert test_config['daq_settings']['server_override'][
            'l1a_generator_settings'][0]['BX'] == 16
    print(test_config.keys())
    assert len(test_config['parameters']) == 1
    assert len(test_config['parameters'][0]) == 2048


def parse_analysis_config(config: dict) -> tuple:
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
    try:
        event_mode = config['event_mode']
        if not isinstance(event_mode, bool):
            raise ConfigFormatError("The event_data field needs to contain a"
                                    " boolean")
    except KeyError:
        event_mode = False
    try:
        analysis_label = config['name']
    except KeyError as err:
        raise ConfigFormatError("The analysis configuration needs"
                                " a name field") from err
    try:
        analysis_object_name = config['python_module_name']
    except KeyError as err:
        raise ConfigFormatError("The analysis configuration needs"
                                " a python_module_name field") from err
    # parse the daq that is required for the analysis
    try:
        daq = config['daq']
    except KeyError as err:
        raise ConfigFormatError("an analysis must specify a daq task") from err

    try:
        iteration_columns = config['iteration_columns']
    except KeyError:
        iteration_columns = None

    analysis_parameters = {}
    if 'parameters' in config.keys():
        if not isinstance(config['parameters'], dict):
            raise ConfigFormatError("The parameters of an analysis must be"
                                    " a dictionary")
        analysis_parameters = config['parameters']
    return {'iteration_columns': iteration_columns,
            'parameters': analysis_parameters,
            'event_mode': event_mode,
            'daq': daq,
            'python_module': analysis_object_name,
            'name': analysis_label,
            'type': 'analysis'}


def test_analysis_config():
    test_fpath = Path('../../examples/analysis_procedures.yaml')
    config = load_configuration(test_fpath)
    parsed_config = parse_analysis_config(config[0])
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
    ptype = entry['type']
    if ptype.lower() == 'daq':
        return parse_scan_config(entry, path)
    if ptype.lower() == 'analysis':
        return parse_analysis_config(entry)
    raise ValueError("The type of a procedure must be"
                     " either daq or analysis")


def test_parse_config_entry():
    scan_test_config = Path('../../tests/configuration/scan_procedures.yaml')
    config = load_configuration(scan_test_config)
    parsed_config = [parse_config_entry(elem, scan_test_config)
                     for elem in config]
    names = ['timewalk_scan', 'timewalk_scan_with_template',
             'timewalk_scan_v2',
             'timewalk_and_phase_scan', 'full_toa_scan',
             'master_tdc_SIG_calibration_daq',
             'master_tdc_REF_calibration_daq']
    for name, entry in zip(names, parsed_config):
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
    print(config)
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
            print(raw_workflows)
            workflows = workflows + validate_wokflow_config(raw_workflows,
                                                            path)
        # The root configuration file can also specify new
        # procedures, similar to libraries
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


def test_parse_config_file():
    config_file = Path('../../tests/configuration/main_config.yaml')
    procedures, workflows = parse_config_file(config_file)
    assert procedures is not None
    assert len(procedures) == 7
    assert len(workflows) == 1


def get_target_config(procedure_config: dict):
    default = procedure_config['target_settings']['power_on_default']
    init = procedure_config['target_settings']['initial_config']
    full_initial = patch_configuration(default, init)
    return full_initial


def get_daq_config(procedure_config: dict):
    default = deepcopy(procedure_config['daq_settings']['default'])
    try:
        server_override = procedure_config['daq_settings']['server_override']
        default = patch_configuration(default, {'server': server_override})
    except KeyError:
        pass
    try:
        client_override = procedure_config['daq_settings']['client_override']
        default = patch_configuration(default, client_override)
    except KeyError:
        pass
    return default


def test_get_daq_config():
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    # test_dir = Path(os.path.dirname(test_fpath))
    scan_configs = []
    test_config = load_configuration(test_fpath)
    for scan in test_config:
        scan_configs.append(parse_scan_config(scan, test_fpath))

    test_config = scan_configs[0]
    default_daq_config = deepcopy(test_config['daq_settings']['default'])
    daq_config = get_daq_config(test_config)
    delta = diff_dict(default_daq_config, daq_config)
    print(delta)
    assert delta is not None
    assert delta['server']['NEvents'] == 1000


def generate_subsystem_states(system_state: dict):
    """
    generate the system state for every subtask given the current system state

    generator to produce the system state for every subtask of the current task
    (most often the DataField task) takes the firs list from the
    scan_parameters and patches the correct part of the subtask config. It also
    removes the first element of the parameters list
    """
    subsystem_state = deepcopy(system_state)
    try:
        subsystem_state['procedure']['parameters'] = system_state[
                'procedure'][
                'parameters'][1:]
    except IndexError:
        subsystem_state['procedure']['parameters'] = []
    for patch in system_state['procedure']['parameters'][0]:
        if 'target' in patch:
            tpatch = patch['target']
            subsystem_state['procedure']['target_settings']['initial_config']\
                = update_dict(system_state['procedure'][
                    'target_settings']['initial_config'], tpatch)
        if 'daq' in patch and len(patch.keys()) == 1:
            dpatch = patch['daq']
            if 'server' in dpatch:
                sp = dpatch['server']
                subsystem_state['procedure']['daq_settings'][
                        'server_override'] = update_dict(
                                system_state['procedure'][
                                             'daq_settings'][
                                             'server_override'], sp)
            if 'client' in dpatch:
                cp = dpatch['client']
                subsystem_state['procedure']['daq_settings'][
                        'client_override'] = update_dict(
                                system_state['procedure'][
                                             'daq_settings'][
                                             'client_override'], cp)
        yield subsystem_state


def test_generate_subsystem_states():
    scan_configs = _get_scan_configs()
    test_config = scan_configs[0]
    system_state = {}
    system_state['procedure'] = test_config
    init = test_config['target_settings']['initial_config']
    patches = test_config['parameters'][0]
    for patch, subscan_system_state in\
            zip(patches, generate_subsystem_states(system_state)):
        assert len(subscan_system_state['procedure']['parameters']) == 0
        sub_init = subscan_system_state[
                'procedure'][
                'target_settings'][
                'initial_config']
        delta = diff_dict(init, sub_init)
        assert {'target': delta} == patch


def generate_run_config(system_state: dict, calibration: dict):
    target_config = get_target_config(system_state['procedure'])
    daq_config = get_daq_config(system_state['procedure'])
    update_dict(target_config, calibration, in_place=True)
    complete_config = {'target': target_config,
                       'daq': daq_config}
    return complete_config


def test_generate_run_configurations():
    pass


def _get_scan_configs():
    """
    Function that makes loading scan configurations a one liner
    instead of copying the code everywhere
    """
    test_fpath = Path('../../tests/configuration/scan_procedures.yaml')
    # test_dir = Path(os.path.dirname(test_fpath))
    scan_configs = []
    test_config = load_configuration(test_fpath)
    for scan in test_config:
        scan_configs.append(parse_scan_config(scan, test_fpath))
    return scan_configs
