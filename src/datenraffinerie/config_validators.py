from schema import Schema, And, Use, Or, Optional,  SchemaError
from pathlib import Path
import yaml
import os


def load_configuration(config_path):
    """
    load the configuration dictionary from a yaml file

    :raises: ConfigFormatError if the input cannot be parsed by the yaml
    parser
    """
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return yaml.safe_load(config_file.read())


current_path = Path('.')


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


systems_settings = Schema(
        {'default': Or(
            [Use(full_path,
                 error="a default config file could not be found")],
            And(str, Use(full_path,
                         error="a default config file could not be found"))),
         Optional('init', defult=[]): Or(
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
                               "range description"))

parameter = Schema(
        Or({'key': [list, str, int],
            'values': parameter_range},
           {'template': str,
            'values': parameter_range},
           error="A parameter must have a 'template' and 'values'"
                 " or 'key' and 'values' field")
)

daq_config = Schema(
        {'name': str,
         'type': 'daq',
         'system_settings': systems_settings,
         Optional('calibration', default=None): str,
         Optional('merge', default=True): bool,
         Optional('mode', default='summary'): Or('summary', 'full'),
         Optional('parameters', default=[]): [parameter],
         Optional('data_columns', default=[]): [str]
         }
)

analysis_config = Schema(
        {'name': str,
         'type': 'analysis',
         'daq': str,
         Optional('compatible_modes', default='summary'):
            Or([Or('summary', 'full')], Or('summary', 'full'),
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


main_config = Schema({
    Optional('libraries', default=[]): [Use(resolve_library)],
    Optional('procedures', default=[]): [procedure_config],
    Optional('workflows', default=[]): [workflow_config]
    })


def test_config_validators():
    import yaml
    import os
    global current_path
    fp = Path('../../tests/configuration/scan_procedures.yaml')
    current_path = Path(os.path.dirname(fp))
    with open(fp.absolute(), 'r') as f:
        configs = yaml.safe_load(f.read())
    fp = Path('../../tests/configuration/analysis_procedures.yaml')
    current_path = Path(os.path.dirname(fp))
    with open(fp.absolute(), 'r') as f:
        configs += yaml.safe_load(f.read())
    for config in configs:
        try:
            validated_config = procedure_config.validate(config)
        except SchemaError as e:
            print(e.code)
            continue
        print(validated_config)
        print()
    fp = Path('../../tests/configuration/main_config.yaml')
    current_path = Path(os.path.dirname(fp))
    with open(fp.absolute(), 'r') as f:
        config = yaml.safe_load(f.read())
    validated_config = main_config.validate(config)
    print(validated_config['workflows'])
