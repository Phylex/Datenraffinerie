"""
Module containing the utilities to parse and properly prepare the configuration
provided by the user

The functions here are testable by calling pytest config_utilities.py
The tests can also be used as a guide on how to use the functions and
what to expect of their behaviour
"""
from pathlib import Path
from copy import deepcopy
from typing import Union
import yaml
import jinja2
import config_validators as cfv
from config_errors import ConfigFormatError
import dict_utils as dtu


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


def generate_patch_from_key(keys: Union[list, str], value):
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
        patch_dict = generate_patch_from_key(key, value)
        assert patch_dict == exd_dict


def build_dimension_patches(scan_dimension):
    scan_values = scan_dimension['values']
    patch_set = []
    try:
        scan_dim_key = scan_dimension['key']
        for val in scan_values:
            patch = generate_patch_from_key(scan_dim_key, val)
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


def test_build_dimension_patches():
    daq_config = load_configuration(
        '../../tests/configuration/scan_procedures.yaml')
    validated_configs = [cfv.procedure_config.validate(config)
                         for config in daq_config]
    scan_dimension = validated_configs[0]['parameters'][0]
    scan_parameters = build_dimension_patches(scan_dimension)
    assert len(scan_parameters) == 2048
    for patch in scan_parameters:
        assert isinstance(patch, dict)

    scan_dimension = daq_config[1]['parameters'][0]
    scan_parameters = build_dimension_patches(scan_dimension)
    assert len(scan_parameters) == 35
    for patch in scan_parameters:
        assert isinstance(patch, dict)
    assert scan_parameters[0]['target']['roc_s0']['ch'][1]['HighRange'] == 1


def build_scan_patches(scan_dim_patch_list: list, current_patch={}):
    patches = []
    if len(scan_dim_patch_list) > 1:
        for scan_dim_patch in scan_dim_patch_list[0]:
            new_cp = dtu.update_dict(current_patch, scan_dim_patch)
            patches += build_scan_patches(scan_dim_patch_list[1:], new_cp)
    else:
        for scan_dim_patch in scan_dim_patch_list[0]:
            patches.append(dtu.update_dict(current_patch, scan_dim_patch))
    return patches


def generate_patches(system_config):
    scan_dim_patches = []
    for dimension in system_config['procedure']['parameters']:
        scan_dim_patches.append(build_dimension_patches(dimension))
    return build_scan_patches(scan_dim_patches)


def generate_init_config(procedure_config: dict):
    config = {}
    init_files = procedure_config['system_settings']['init']
    init_config_fragments = [load_configuration(icp) for icp in init_files]
    for frag in init_config_fragments:
        dtu.update_dict(config, frag, in_place=True)
    override = procedure_config['system_settings']['override']
    dtu.update_dict(config, override, in_place=True)
    return config


def generate_system_default_config(procedure_config: dict):
    config = {}
    default_config_fragments = [
            load_configuration(dcp)
            for dcp in procedure_config['system_settings']['default']]
    for frag in default_config_fragments:
        dtu.update_dict(config, frag, in_place=True)
    return config


def test_get_system_config():
    test_configs = _get_daq_configs()
    test_config = test_configs[0]
    default_daq_config = load_configuration(
            test_config['system_settings']['default'][1])['daq']
    system_default_config = generate_system_default_config(test_config)['daq']
    print(system_default_config)
    delta = dtu.diff_dict(default_daq_config, system_default_config)
    assert delta is None


def generate_worker_state(system_state: dict):
    """
    create procedure configrurations that can be distributed to the worker
    tasks.

    Do this by figuring out how many runs there are and how many workers there
    and then modifying the parameters section of the procedure configuration
    for each worker so that the worker will work through roughly 1/nworker
    of the runs
    """
    values = [dim['values']
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


def test_generate_worker_states():
    scan_configs = _get_daq_configs()
    test_config = scan_configs[0]
    reference_dim = [len(dim['values'])
                     for dim in test_config['parameters']]
    system_state = {}
    system_state['workers'] = 1
    system_state['procedure'] = test_config
    for state in generate_worker_state(system_state):
        parameters = state['procedure']['parameters']
        tree_dim = [len(dim['values']) for dim in parameters]
        assert tree_dim == reference_dim
    system_state = {}
    system_state['workers'] = 3
    system_state['procedure'] = test_config
    for i, state in enumerate(generate_worker_state(system_state)):
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
    for i, state in enumerate(generate_worker_state(system_state)):
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
    for i, config in enumerate(test_config):
        cfv.current_path = test_fpath
        test_config[i] = cfv.procedure_config.validate(config)
    return test_config
