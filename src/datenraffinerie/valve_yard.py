"""
The ValveYard is a class in the datenraffinerie that is responsible
for parsing the user configuration and requiring the right scan or
analysis task and passing it all necessary values from their proper
functioning

Author: Alexander Becker (a.becker@cern.ch)
Date: 2021-12-16
"""
import os
from pathlib import Path
from copy import deepcopy
import luigi
import shutil
import logging
from .scan import DataField, Fracker
from .distillery import Distillery
from . import config_utilities as cfu
from . import control_adapter as ctrl
from . import analysis_utilities as anu

module_logger = logging.getLogger(__name__)


class ValveYard(luigi.Task):
    system_state = luigi.DictParameter(significant=True)
    priority = luigi.OptionalParameter(significant=False, default=0)

    def output(self):
        """
        determin the files that are to be returned by the ValveYard to them
        calling tasks

        if the tasks are run in event mode, the output files
        are not concatenated but are instead just passed along to the
        calling task

        as this is the first method called during execution of the ValveYard,
        also determin if the
        """
        root_cfg_file = self.system_state['root_config_path']
        procedure_name = self.system_state['name']
        if 'event_mode' not in self.system_state:
            if "procedure" in self.system_state:
                proc = self.system_state['procedure']
            else:
                proc = None
            if self.detrmin_daq_mode(root_cfg_file, procedure_name, proc)\
                    == "event_mode":
                self.system_state['event_mode'] = True
            else:
                self.system_state["event_mode"] = False
        if self.system_state['event_mode']\
           or not isinstance(self.input()['data'], list):
            output = {'full-calibration': self.input()['full-calibration'],
                      'data': self.input()['data']}
            return output
        else:
            output_directory = self.system_state['output_path']
            out = Path(output_directory) / procedure_name \
                                         / f"{procedure_name}_merged.h5"
            output = {'full-calibration': self.input()['full-calibration'],
                      'data': luigi.LocalTarget(out)}
            return output

    def requires(self):
        """ A wrapper that parses the configuration and starts the procedure
        with the corresponding procedure label

        :raises: ConfigFormatError if either the type of the configuration
            entry
            does not match the allowed ones or if the YAML is malformed
        :raises: DAQConfigError if the DAQ configuration is malformed
        """
        root_cfg_file = self.system_state['root_config_path']
        procedure_name = self.system_state['name']

        # create the directory structure
        data_dir = Path(self.system_state['output_path'])
        output_dir = data_dir / procedure_name
        if not data_dir.exists():
            os.makedirs(data_dir)
        if not output_dir.exists():
            os.makedirs(output_dir)
        subtask_state = deepcopy(self.system_state)
        subtask_state['output_path'] = output_dir.resolve()

        dependencies = []
        # properly start the dependent tasks and respect the recursability
        if 'procedure' not in self.system_state:
            procedure = ValveYard.get_procedure_with_name(root_cfg_file,
                                                          procedure_name)
        else:
            procedure = self.system_state['procedure']
        if not isinstance(procedure, list):
            procedure = [procedure]
        ValveYard._parse_procedure_list(procedure,
                                        subtask_state,
                                        dependencies,
                                        1000)
        return dependencies

    def run(self):
        # check if the procedure that was executed handles 'raw' data and if so
        # do not concatenate the files but simply pass them on
        if self.system_state['event_mode']:
            return self.input()
        if not isinstance(self.input(), list):
            return self.input()

        # run the compiled turbo pump if available
        # otherwise run the python version
        # remove the files that where merged together when done
        in_files = [data_file.path for data_file in self.input()]
        if shutil.which('turbo-pump') is not None:
            if len(in_files) == 1:
                shutil.copy(in_files[0], self.output().path)
                return
            result = anu.run_turbo_pump(self.output().path, in_files)
            if result != 0:
                raise RuntimeError("turbo-pump crashed")
        else:
            anu.merge_files(in_files, self.output().path)
        for file in in_files:
            os.remove(file)

    @staticmethod
    def _parse_procedure_list(proc_list, system_state, dependencies, priority):
        """
        Method that adds the correct task for any element of the procedure list

        This method handles recursion properly by also adding all elementsfrom
        from workflows inside workflows. The tasks use luigis priority concept
        to execute in the order specified in the workflow. This assumes that
        the Distilleries and DataField/Fracker tasks have dependencies of their
        own.

        Parameters
        ----------
        proc_list: list
            (nested) list of the procedures that are to be executed by them
            ValveYard
        system_state: dict
            the system state of the ValveYard task being executed (it may be
            altered for the child tasks)
        dependencies: list
            list that is filled with the actual luigi tasks that correspond
            to the specifications of the config
        priority: int
            The priority of the next task to be executed. This is decremented
            for every task should be executed by the ValveYard

        Returns
        -------
        priority: int
            The priority after adding all the tasks on it's level to the list
            this needs to be returned so that the execution order is maintained
            even for nested list workflows

        Notes
        -----
        This method is used exclusively inside the ValveYard and is not
        intended for use by methods outside those of the ValveYard class
        """
        for i, procedure in enumerate(proc_list):
            print(procedure['name'])
            subprocess_state = deepcopy(system_state)
            subprocess_state['procedure'] = procedure
            if not isinstance(procedure, list):
                if procedure['type'] == 'analysis':
                    dependencies.append(
                        Distillery(system_state=subprocess_state,
                                   priority=priority))
                elif procedure['type'] == 'daq':
                    if len(procedure['parameters']) == 1\
                       and system_state['loop']:
                        dependencies.append(
                                Fracker(system_state=subprocess_state,
                                        id=0,
                                        priority=priority))
                    else:
                        dependencies.append(
                                DataField(system_state=subprocess_state,
                                          id=0,
                                          priority=priority))
                else:
                    raise cfu.ConfigFormatError(
                            "The type of an entry must be either "
                            "'daq' or 'analysis'")
                priority = priority - 1
            else:
                priority = ValveYard._parse_procedure_list(procedure,
                                                           system_state,
                                                           dependencies,
                                                           priority)
        return priority

    @staticmethod
    def detrmin_daq_mode(root_config_path, procedure_name, procedure=None):
        if procedure is None:
            procedure = ValveYard.get_procedure_with_name(root_config_path,
                                                          procedure_name)
        if not isinstance(procedure, list):
            try:
                if procedure['event_mode']:
                    return "event_mode"
            except KeyError:
                pass
        else:
            for proc in procedure:
                if isinstance(proc, list):
                    mode = ValveYard.detrmin_daq_mode(
                                root_config_path,
                                procedure_name, proc)
                    if mode == "event_mode":
                        return mode
                else:
                    if proc['event_mode']:
                        return "event_mode"
        return "summary_mode"

    @staticmethod
    def get_procedure_with_name(root_cfg_file, procedure_name,
                                procedures=None, workflows=None):
        if procedures is None and workflows is None:
            procedures, workflows = cfu.parse_config_file(root_cfg_file)
        procedure_names = list(map(lambda p: p['name'], procedures))
        workflow_names = list(map(lambda w: w['name'], workflows))
        # check if the name given is in the procedures list.
        if procedure_name in procedure_names:
            procedure_index = procedure_names.index(procedure_name)
            procedure = procedures[procedure_index]
            return procedure
        # check if the name is in the list of workflows
        elif procedure_name in workflow_names:
            workflow_index = workflow_names.index(procedure_name)
            workflow = workflows[workflow_index]
            return [ValveYard.get_procedure_with_name(root_cfg_file, task_name,
                                                      procedures, workflows)
                    for task_name in workflow['tasks']]
        else:
            raise ctrl.DAQConfigError(f"No '{procedure_name}' found in"
                                      f" the config file {root_cfg_file}")


def test_get_procedure_with_name():
    # test the base case where the procedure name is not nested
    root_cfg_file = Path('../../tests/configuration/main_config.yaml')
    procedure_name = 'timewalk_scan'
    procedures = ValveYard.get_procedure_with_name(
            root_cfg_file,
            procedure_name)
    assert procedures['name'] == procedure_name
    assert isinstance(procedures['parameters'], list)
    assert len(procedures['parameters']) == 1
    assert len(procedures['parameters'][0]) == 2048
    assert isinstance(procedures['parameters'][0][0], dict)
    assert isinstance(procedures['target_settings']['power_on_default'], dict)

    procedure_name = 'master_tdc_daq'
    procedures = ValveYard.get_procedure_with_name(
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


def test_determine_daq_mode():
    root_cfg_file = Path('../../tests/configuration/main_config.yaml')
    procedure_name = 'timewalk_scan'
    assert ValveYard.detrmin_daq_mode(root_cfg_file, procedure_name)\
        == 'summary_mode'
    procedure_name = 'master_tdc_daq'
    assert ValveYard.detrmin_daq_mode(root_cfg_file, procedure_name)\
        == 'event_mode'


def test_parse_procedure_list():
    root_cfg_file = Path('../../tests/configuration/main_config.yaml')
    procedure_name = 'master_tdc_daq'
    system_state = {}
    dependencies = []
    system_state['loop'] = False
    system_state['event_mode'] = True
    procedures = ValveYard.get_procedure_with_name(
            root_cfg_file,
            procedure_name)
    assert isinstance(procedures, list)
    assert len(procedures) == 2
    assert procedures[0]['name'] == 'master_tdc_SIG_calibration_daq'
    assert procedures[1]['name'] == 'master_tdc_REF_calibration_daq'
    priority = ValveYard._parse_procedure_list(procedures,
                                               system_state,
                                               dependencies,
                                               1000)
    assert len(dependencies) == 2
    assert isinstance(dependencies[0], DataField)
    assert isinstance(dependencies[1], DataField)
    assert dependencies[0].system_state['procedure']['name']\
        == procedures[0]['name']
    for i, dep in enumerate(dependencies):
        assert dep.priority == 1000 - i

    assert priority == 998
