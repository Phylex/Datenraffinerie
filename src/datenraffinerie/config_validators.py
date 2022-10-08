from schema import Schema, And, Use, Or, Optional
from pathlib import Path
import yaml
import os


current_path = Path('.')


def set_current_path(path):
    global current_path
    current_path = path


def load_configuration(config_path):
    """
    load the configuration dictionary from a yaml file

    :raises: ConfigFormatError if the input cannot be parsed by the yaml
    parser
    """
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return yaml.safe_load(config_file.read())


def full_path(path):
    global current_path
    fpath = Path(current_path) / path
    if fpath.exists():
        return fpath.resolve()
    raise FileNotFoundError(f'{fpath.resolve()} cannot be found')


def generate_values(rdict):
    stop = rdict['stop']
    try:
        start = rdict['start']
    except KeyError:
        start = 0
    try:
        step = rdict['step']
    except KeyError:
        step = 1
    return list(range(start, stop, step))


def resolve_library(path):
    global current_path
    path = Path(path)
    path = Path(current_path) / path
    if not os.path.exists(path.absolute()):
        raise FileNotFoundError(
                f"The config file {path.resolve()} cant be found")
    tmp_path = current_path
    current_path = os.path.dirname(path)
    validated_lib = library_file.validate(load_configuration(path))
    current_path = tmp_path
    return validated_lib


systems_settings = Schema(
        {'default': Or(
            [Use(full_path,
                 error="a default config file could not be found")],
            And(str, Use(full_path,
                         error="a default config file could not be found"))),
         Optional('init', default=[]): Or(
             [Use(full_path,
                  error="an init config file coule not be found")],
             And(str, Use(full_path,
                          error="an init config file coule not be found"))),
         Optional('override', default={}): dict})


parameter_range = Schema(
        Or(
            And(dict, Use(generate_values,
                          error='values field is not a range description')),
            [dict, int], error="values is neither a list values nor a "
                               "range description")
         )

parameter = Schema(
        Or({'key': [list, str, int],
            'values': parameter_range},
           {'template': str,
            'values': parameter_range,
            'default': str},
           error="A parameter must have a 'template', "
                 "'values' and 'default' field "
                 " or 'key' and 'values' field")
         )

daq_config = Schema(
        {'name': str,
         'type': 'daq',
         'system_settings': systems_settings,
         Optional('calibration', default=None): str,
         Optional('merge', default=True): bool,
         Optional('run_start_tdc_procedure', default=False): bool,
         Optional('repeat', default=1): int,
         Optional('mode', default='summary'): Or('summary', 'full'),
         Optional('data_format', default='raw'): Or('raw', 'characterisation'),
         Optional('parameters', default=None): [parameter],
         Optional('data_columns', default=[]): [str]
         }
)

analysis_config = Schema(
        {'name': str,
         'type': 'analysis',
         'daq': str,
         Optional('compatible_modes', default='summary'):
            Or('summary', 'full',
               error="compatible modes are either 'summary' or 'full'"),
         Optional('provides_calibration', default=False): bool,
         Optional('module_name'): str,
         Optional('parameters', default={}): dict
         }
)

procedure_config = Schema(Or(analysis_config, daq_config))

workflow_config = Schema({'name': str,
                          'tasks': [str]})

library_file = Schema([procedure_config])


main_config = Schema({
    Optional('libraries', default=[]): [Use(resolve_library)],
    Optional('procedures', default=[]): [procedure_config],
    Optional('workflows', default=[]): [workflow_config]
    })
