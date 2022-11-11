from pathlib import Path


def flatten(nested_list: list) -> list:
    flattened_list = []
    for elem in nested_list:
        if isinstance(elem, list):
            flattened_list += flatten(elem)
        else:
            flattened_list.append(elem)
    return flattened_list


def test_flatten():
    tlist = [1, 2, 3, [4, 5, 6], [[7, 8], [9, 10], 11, 12], [13], 14, 15]
    flattened_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    assert flatten(tlist) == flattened_list

    tlist = [1, 2, 3, []]
    flattened_list = [1, 2, 3]
    assert flatten(tlist) == flattened_list


def get_procedure_with_name(procedure_names,
                            procedures, workflows):
    avail_proc_names = [p['name'] for p in procedures]
    workflow_names = [w['name'] for w in workflows]
    # check if the name given is in the procedures list.
    procedures = []
    for procedure_name in procedure_names:
        if procedure_name in avail_proc_names:
            procedure_index = procedure_names.index(procedure_name)
            procedure = procedures[procedure_index]
            procedures.append(procedure)
        # check if the name is in the list of workflows
        elif procedure_name in workflow_names:
            workflow_index = workflow_names.index(procedure_name)
            workflow = workflows[workflow_index]
            procedures.append([get_procedure_with_name(task_name,
                                                       procedures,
                                                       workflows)
                               for task_name in workflow['tasks']])
    return flatten(procedures)


def test_get_procedure_with_name():
    # test the base case where the procedure name is not nested
    root_cfg_file = Path('../../tests/configuration/main_config.yaml')
    procedure_name = 'timewalk_scan'
    procedures = get_procedure_with_name(
            root_cfg_file,
            procedure_name)
    assert procedures['name'] == procedure_name
    assert isinstance(procedures['parameters'], list)
    assert len(procedures['parameters']) == 1
    assert len(procedures['parameters'][0]) == 2048
    assert isinstance(procedures['parameters'][0][0], dict)
    assert isinstance(procedures['target_settings']['power_on_default'], dict)

    procedure_name = 'master_tdc_daq'
    procedures = get_procedure_with_name(
            root_cfg_file,
            procedure_name)
    assert isinstance(procedures, list)
    assert len(procedures) == 2
    assert procedures[0]['name'] == 'master_tdc_SIG_calibration_daq'
    assert procedures[1]['name'] == 'master_tdc_REF_calibration_daq'
    assert 'parameters' in procedures[0]
    assert 'parameters' in procedures[1]
    assert 'data_columns' in procedures[0]
    assert len(procedures[0]['data_columns']) == 13
