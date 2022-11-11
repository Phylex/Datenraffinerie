"""
Module containing the utilities to parse and properly prepare the configuration
provided by the user

The functions here are testable by calling pytest config_utilities.py
The tests can also be used as a guide on how to use the functions and
what to expect of their behaviour
"""
from copy import deepcopy
from typing import Union
import yaml
import jinja2
import os
from .config_errors import ConfigFormatError
from . import dict_utils as dtu
from . import config_validators as cvd
import logging
from itertools import chain


def get_procedure_configs(main_config_file: str, procedure_name: str,
                          calibration: dict = None, diff: bool = False):
    cvd.set_current_path(os.path.dirname(main_config_file))
    with open(main_config_file, 'r') as cfp:
        config = yaml.safe_load(cfp.read())
    config = cvd.main_config.validate(config)
    available_procedures = config['procedures'] + \
        list(chain(*config['libraries']))
    try:
        procedure = list(filter(lambda x: x['name'] == procedure_name,
                                available_procedures))[0]
    except IndexError:
        all_procedure_names = list(map(lambda x: x['name'],
                                   available_procedures))
        logging.critical(f"The procedure with name: {procedure_name} "
                         "could not be found, Available procedures are: "
                         f"{all_procedure_names}")
        raise ValueError("Procedure could not be found",
                         procedure_name, all_procedure_names)
    return procedure, generate_configurations(procedure, calibration, diff)


def generate_configurations(procedure: dict, calibration: dict = None,
                            diff: bool = False):
    """
    Given a procedure entry loaded from the config file, generate
    the configurations necessary for every run of the procedure
    """
    system_default_config = generate_system_default_config(procedure)
    system_init_config = generate_init_config(procedure)
    scan_patches = generate_patches(procedure)
    if calibration is not None:
        dtu.update_dict(system_init_config, calibration, in_place=True)
    if diff:
        full_system_init_config = dtu.update_dict(system_default_config,
                                                  system_init_config)
        system_init_config = dtu.diff_dict(system_default_config,
                                           full_system_init_config)
        current_state = full_system_init_config.copy()

        def run_config_generator():
            for _ in range(procedure['repeat']):
                for patch in scan_patches:
                    run_config = dtu.update_dict(full_system_init_config,
                                                 patch)
                    run_config_diff = dtu.diff_dict(current_state, run_config)
                    if run_config_diff is not None:
                        dtu.update_dict(current_state,
                                        run_config_diff,
                                        in_place=True)
                        yield run_config_diff
                    else:
                        yield {}
    else:
        system_init_config = dtu.update_dict(system_default_config,
                                             system_init_config)

        def run_config_generator():
            for _ in range(procedure['repeat']):
                for patch in scan_patches:
                    yield dtu.update_dict(system_init_config, patch)
    return system_default_config, system_init_config, run_config_generator(), \
        len(scan_patches) * procedure['repeat']


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


def build_dimension_patches(scan_dimension):
    scan_values = scan_dimension['values']
    patch_set = []
    default_set = []
    try:
        scan_dim_key = scan_dimension['key']
        for val in scan_values:
            patch = generate_patch_from_key(scan_dim_key, val)
            patch_set.append(patch)
            default_set.append({})
        return patch_set, default_set
    except KeyError:
        try:
            template = scan_dimension['template']
            default_template = scan_dimension['default']
            template = jinja2.Template(template)
            default_template = jinja2.Template(default_template)
            patch_set.append(
                yaml.safe_load(template.render(value=scan_values[0])))
            for prev_val, val in zip(scan_values[:-1], scan_values[1:]):
                default_set.append(
                    yaml.safe_load(default_template.render(value=prev_val)))
                patch_set.append(yaml.safe_load(template.render(value=val)))
            default_set.append(
                yaml.safe_load(default_template.render(value=scan_values[-1])))
            return patch_set, default_set
        except jinja2.TemplateSyntaxError as e:
            raise ConfigFormatError(
                f"The template is malformed: {e.message}")
        except KeyError:
            raise ConfigFormatError(
                "Neither the template keyword nor the 'key' keyword"
                " could not be found")


def build_scan_patches(scan_dim_patches: list, default: dict,
                       current_patch={}):
    patches = []
    if len(scan_dim_patches) > 1:
        for scan_dim_patch in scan_dim_patches[0]:
            new_cp = default
            new_cp = dtu.update_dict(current_patch, scan_dim_patch)
            patches += build_scan_patches(scan_dim_patches[1:],
                                          default,
                                          new_cp)
    else:
        for scan_dim_patch in scan_dim_patches[0]:
            patch = default
            patch = dtu.update_dict(patch, current_patch)
            patch = dtu.update_dict(patch, scan_dim_patch)
            patches.append(patch)
    return patches


def generate_patches(procedure_config):
    scan_dim_patches = []
    scan_dim_defaults = []
    if procedure_config['parameters'] is None:
        return [{}]
    for dimension in procedure_config['parameters']:
        dim_patches, dim_defaults = build_dimension_patches(dimension)
        scan_dim_patches.append(dim_patches)
        scan_dim_defaults += dim_defaults
    complete_deflt = {}
    for deflt in scan_dim_defaults:
        complete_deflt = dtu.update_dict(complete_deflt, deflt)
    return build_scan_patches(scan_dim_patches, default=complete_deflt)


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
