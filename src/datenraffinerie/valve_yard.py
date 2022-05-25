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
    root_config_file = luigi.Parameter(significant=True)
    procedure_label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    analysis_module_path = luigi.Parameter(significant=True)
    network_config = luigi.DictParameter(significant=True)
    loop = luigi.BoolParameter(significant=True)
    priority = luigi.OptionalParameter(significant=False, default=0)

    def output(self):
        if self.detrmin_daq_mode(self.root_config_file, self.procedure_label) == "event_mode"\
           or not isinstance(self.input(), list):
            return self.input()
        else:
            out = Path(self.output_dir) / self.procedure_label \
                    / f"{self.procedure_label}_merged.h5"
            return luigi.LocalTarget(out)

    def requires(self):
        """ A wrapper that parses the configuration and starts the procedure
        with the corresponding procedure label

        :raises: ConfigFormatError if either the type of the configuration entry
            does not match the allowed ones or if the YAML is malformed
        :raises: DAQConfigError if the DAQ configuration is malformed
        """
        logger = module_logger.getChild('ValveYard.requires')
        data_dir = Path(self.output_dir)
        if not data_dir.exists():
            os.makedirs(data_dir)
        procedures, workflows = cfu.parse_config_file(self.root_config_file)
        logger.debug(procedures)
        logger.debug(workflows)
        procedure_names = list(map(lambda p: p['name'], procedures))
        workflow_names = list(map(lambda w: w['name'], workflows))
        procedure = None
        workflow = None
        # check if the name given is in the procedures list.
        if self.procedure_label in procedure_names:
            try:
                procedure_index = procedure_names.index(self.procedure_label)
            except ValueError:
                logger.critical(f'{self.procedure_label} is not in the list of procedures of {self.root_config_path}')
                return None
            procedure = procedures[procedure_index]
        # check if the name is in the list of workflows
        elif self.procedure_label in workflow_names:
            try:
                workflow_index = workflow_names.index(self.procedure_label)
                workflow = workflows[workflow_index]
            except ValueError as e:
                logger.critical(f"{self.procedure_label} is not in the list of workflows of {self.root_config_file}")
                raise e

        else:
            raise ctrl.DAQConfigError(f"No '{self.procedure_label}' found in"
                                      f" the config file {self.root_config_file}")
        output_dir = data_dir / self.procedure_label
        if not output_dir.exists():
            os.makedirs(output_dir)
        if workflow is not None:
            wf_procedures = workflow['tasks']
            if not isinstance(wf_procedures, list):
                raise ctrl.DAQConfigError("The content of the task"
                                          f" field of workflow {workflow.name}"
                                          f" needs to be a list")
            dependencies = []
            for i, task in enumerate(wf_procedures):
                dependencies.append(ValveYard(self.root_config_file,
                                              task,
                                              output_dir,
                                              self.analysis_module_path,
                                              self.network_config,
                                              self.loop,
                                              priority=len(wf_procedures)-i))
            return dependencies

        # select between workflows and procedures
        if procedure is not None:
            if procedure['type'] == 'analysis':
                return Distillery(name=self.procedure_label,
                                  python_module=procedure['python_module'],
                                  daq=procedure['daq'],
                                  output_dir=str(output_dir.resolve()),
                                  parameters=procedure['parameters'],
                                  root_config_path=str(
                                      Path(self.root_config_file).resolve()),
                                  analysis_module_path=self.analysis_module_path,
                                  network_config=self.network_config,
                                  loop=self.loop,
                                  event_mode=True if self.detrmin_daq_mode(self.root_config_file, procedure['daq']) == "event_mode" else False,
                                  sort_by=procedure['iteration_columns'])
            if procedure['type'] == 'daq':
                if len(procedure['parameters']) == 1 and self.loop:
                    return Fracker(identifier=0,
                                   label=self.procedure_label,
                                   output_dir=str(output_dir.resolve()),
                                   output_format='hdf5',
                                   scan_parameters=procedure['parameters'],
                                   target_config=procedure['target_init_config'],
                                   target_default_config=procedure['target_power_on_default_config'],
                                   daq_system_config=procedure['daq_system_config'],
                                   daq_system_default_config=procedure['daq_system_default_config'],
                                   root_config_path=str(
                                       Path(self.root_config_file).resolve()),
                                   calibration=procedure['calibration'],
                                   analysis_module_path=self.analysis_module_path,
                                   network_config=self.network_config,
                                   loop=self.loop,
                                   raw=procedure['raw'],
                                   data_columns=procedure['data_columns'])
                return DataField(identifier=0,
                                 label=self.procedure_label,
                                 output_dir=str(output_dir.resolve()),
                                 output_format='hdf5',
                                 scan_parameters=procedure['parameters'],
                                 target_config=procedure['target_init_config'],
                                 target_default_config=procedure['target_power_on_default_config'],
                                 daq_system_config=procedure['daq_system_config'],
                                 daq_system_default_config=procedure['daq_system_default_config'],
                                 root_config_path=str(
                                     Path(self.root_config_file).resolve()),
                                 calibration=procedure['calibration'],
                                 analysis_module_path=self.analysis_module_path,
                                 network_config=self.network_config,
                                 loop=self.loop,
                                 raw=procedure['raw'],
                                 data_columns=procedure['data_columns']) # indicate if to produce event by event data data
            raise cfu.ConfigFormatError("The type of an entry must be either "
                                        "'daq' or 'analysis'")

    def run(self):
        # check if the procedure that was executed handles 'raw' data and if so 
        # do not concatenate the files but simply pass them on
        if self.detrmin_daq_mode(self.root_config_file, self.procedure_label)\
                == "event_mode":
            return self.input()
        if not isinstance(self.input(), list):
            return
        in_files = [data_file.path for data_file in self.input()]
        # run the compiled turbo pump if available
        if shutil.which('turbo-pump') is not None:
            if len(in_files) == 1:
                shutil.copy(in_files[0], self.output().path)
                return
            result = anu.run_turbo_pump(self.output().path, in_files)
            if result != 0:
                raise RuntimeError("turbo-pump crashed")
        # otherwise run the python version
        else:
            anu.merge_files(in_files, self.output().path, self.raw)
        for file in in_files:
            os.remove(file)

    @staticmethod
    def detrmin_daq_mode(root_config_path, procedure_name):
        procedures, workflows = cfu.parse_config_file(root_config_path)
        procedure_names = list(map(lambda p: p['name'], procedures))
        workflow_names = list(map(lambda w: w['name'], workflows))
        procedure = None
        workflow = None
        if procedure_name in procedure_names:
            try:
                procedure_index = procedure_names.index(procedure_name)
            except ValueError:
                logger.critical(f'{procedure_name} is not in the list of procedures of {root_config_path}')
                return None
            procedure = procedures[procedure_index]
        elif procedure_name in workflow_names:
            try:
                workflow_index = workflow_names.index(procedure_name)
                workflow = workflows[workflow_index]
            except ValueError as e:
                logger.critical(f"{procedure_name} is not in the list of workflows of {root_config_path}")
        else:
            raise ctrl.DAQConfigError(f"No '{procedure_name}' found in"
                                      f" the config file {root_config_path}")
        if procedure is not None:
            try:
                if procedure['raw']:
                    return "event_mode"
            except KeyError:
                    pass
        else:
            for procedure_name in workflow['tasks']:
                try:
                    procedure_index = procedure_names.index(procedure_name)
                    procedure = procedures[procedure_index]
                except IndexError:
                    continue
                try:
                    if procedure['raw']:
                        return "event_mode"
                except KeyError:
                    pass
        return "summary_mode"

def test_daq_mode():
    pass
