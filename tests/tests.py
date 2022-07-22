from pathlib import Path
import pytest
from datenraffinerie.config_validators import procedure_config
from datenraffinerie.config_validators import main_config
from datenraffinerie.config_validators import set_current_path
from datenraffinerie.config_utilities import generate_patch_from_key
from datenraffinerie.dict_utils import diff_dict
from datenraffinerie.dict_utils import update_dict
from datenraffinerie.config_utilities import load_configuration
from datenraffinerie.config_utilities import build_dimension_patches
from datenraffinerie.config_utilities import build_scan_patches
import os
import yaml


@pytest.mark.parametrize("config_path, iterate, validator", [
    (Path('configuration/scan_procedures.yaml'), True, procedure_config),
    (Path('configuration/analysis_procedures.yaml'), True, procedure_config),
    (Path('configuration/main_config.yaml'), False, main_config)
    ])
def test_config_validators(config_path, iterate, validator):
    set_current_path(Path(os.path.dirname(config_path)))
    with open(config_path.absolute(), 'r') as f:
        configs = yaml.safe_load(f.read())
    if iterate:
        for config in configs:
            _ = validator.validate(config)
    else:
        validator.validate(configs)


@pytest.mark.parametrize("input_key, input_value, expected", [
    ([['k1', 'k2', 'k3'], 'k4', 'k5'], 1,
     {'k1': {'k4': {'k5': 1}},
      'k2': {'k4': {'k5': 1}},
      'k3': {'k4': {'k5': 1}}}
     ),
    (['daq', ['k1', 'k2', 'k3'], 'k4', 'k5'], 1,
     {'daq': {'k1': {'k4': {'k5': 1}},
              'k2': {'k4': {'k5': 1}},
              'k3': {'k4': {'k5': 1}}}}
     ),
    (['daq', ['k1', 'k2', 'k3'], ['k4', 'k5'], 'k6'], 3,
     {'daq': {'k1': {'k4': {'k6': 3},
                     'k5': {'k6': 3}},
              'k2': {'k4': {'k6': 3},
                     'k5': {'k6': 3}},
              'k3': {'k4': {'k6': 3},
                     'k5': {'k6': 3}}
              }
      }
     )
    ])
def test_patch_generator(input_key, input_value, expected):
    patch_dict = generate_patch_from_key(input_key, input_value)
    assert patch_dict == expected


@pytest.mark.parametrize("original, update, expected, in_place", [
    ({'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'},
     {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5]},
     {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5], 'that': 'what'},
     False
     ),
    ({'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'},
     {},
     {'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'},
     False,
     ),
    ({'this': [{'a': 1}, {'b': 2}, {'c': 3}, 3], 'that': 'what'},
     {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5]},
     {'this': [{'a': 3}, {'b': 3}, {'c': 5}, 5], 'that': 'what'},
     True
     ),
    ])
def test_update_dict(original, update, expected, in_place):
    if in_place:
        update_dict(original, update, in_place=True)
        assert original == expected
    else:
        updated_dict = update_dict(original, update)
        assert updated_dict == expected


@pytest.mark.parametrize("in_1, in_2, diff", [
    ({'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3},
     {'a': 2, 'b': {'c': 3, 'f': 4}, 'e': 3, 'g': 4},
     {'a': 2, 'b': {'c': 3}, 'g': 4}
     ),
    ({'a': 1, 'b': {'c': 2, 'f': 4}, 'e': 3},
     {'a': 2, 'b': {'c': 2, 'f': 5}, 'e': 4, 'g': 4},
     {'a': 2, 'b': {'f': 5}, 'g': 4, 'e': 4}
     ),
    ])
def test_diff_dict(in_1, in_2, diff):
    result = diff_dict(in_1, in_2)
    assert result == diff


@pytest.mark.parametrize("config_file, procedure_name, parameter_patches", [
    ('configuration/test_procedures.yaml',
     'test_1',
     [
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}}},
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}}},
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 10}, 1: {'Calib': 10}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 10}, 1: {'Calib': 10}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 10}, 1: {'Calib': 10}}}},
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 15}, 1: {'Calib': 15}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 15}, 1: {'Calib': 15}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 15}, 1: {'Calib': 15}}}},
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 20}, 1: {'Calib': 20}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 20}, 1: {'Calib': 20}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 20}, 1: {'Calib': 20}}}}
     ]
     ),
    ('configuration/test_procedures.yaml',
     'test_2',
     [
         {'roc_s0': {'Top': {0: {'phase_strobe': 0}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 0}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 0}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 2}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 2}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 2}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 4}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 4}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 4}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 6}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 6}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 6}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 8}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 8}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 8}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 10}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 10}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 10}}}}]
     )
])
def test_build_dimension_patches(config_file, procedure_name,
                                 parameter_patches):
    config_struct = load_configuration(config_file)
    validated_configs = [procedure_config.validate(config)
                         for config in config_struct]
    test_procedure = list(filter(lambda x: x['name'] == procedure_name,
                          validated_configs))[0]
    scan_dimension = test_procedure['parameters'][0]
    scan_parameters = build_dimension_patches(scan_dimension)
    assert scan_parameters == parameter_patches


@pytest.mark.parametrize("dimensional_patch_sets, outputs", [
    ([[
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}}}},
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}}}},
      ],
      [
         {'roc_s0': {'Top': {0: {'phase_strobe': 0}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 0}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 0}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 2}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 2}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 2}}}},
         {'roc_s0': {'Top': {0: {'phase_strobe': 4}}},
          'roc_s1': {'Top': {0: {'phase_strobe': 4}}},
          'roc_s2': {'Top': {0: {'phase_strobe': 4}}}},
       ]
      ],
     [
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 0}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 0}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 0}}}
          },
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 2}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 2}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 2}}}
          },
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 4}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 4}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 0}, 1: {'Calib': 0}},
                     'Top': {0: {'phase_strobe': 4}}}
          },
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 0}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 0}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 0}}}
          },
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 2}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 2}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 2}}}
          },
         {'roc_s0': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 4}}},
          'roc_s1': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 4}}},
          'roc_s2': {'ReferenceVoltage': {0: {'Calib': 5}, 1: {'Calib': 5}},
                     'Top': {0: {'phase_strobe': 4}}}
          }
      ]
     ),
])
def test_build_scan_patches(dimensional_patch_sets, outputs):
    assert outputs == build_scan_patches(dimensional_patch_sets)
