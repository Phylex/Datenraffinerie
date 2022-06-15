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
import yaml
import logging
from .scan import DataField
from .distillery import Distillery
from . import config_utilities as cfu
from . import dict_utils as dtu
from . import config_validators as cfv
from . import control_adapter as ctrl
from . import vlvyrd_utils as vyu


module_logger = logging.getLogger(__name__)


class ValveYard(luigi.Task):
    system_state = luigi.DictParameter(significant=True)
    task_name = luigi.Parameter(significant=True)
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

        output_directory = Path(self.system_state['output_path'])
        input = self.input()
        output = {}
        output['data'] = [i['data'] for i in input]
        output['full-calibration'] = Path(output_directory) /\
            str(self.task_name) + '-full-calibration.yaml'
        return output

    def requires(self):
        """ A wrapper that parses the configuration and starts the procedure
        with the corresponding procedure label

        :raises: ConfigFormatError if either the type of the configuration
            entry
            does not match the allowed ones or if the YAML is malformed
        :raises: DAQConfigError if the DAQ configuration is malformed
        """
        self.system_state = cfu.unfreeze(self.system_state)
        root_cfg_file = self.system_state['root_config_path']
        cfv.current_path = Path(root_cfg_file)
        configuration = cfv.main_config.validate(root_cfg_file)
        output_directory = Path(self.system_state['output_path'])

        available_procedures = configuration['procedures']\
            + configuration['libraries']
        available_workflows = configuration['workflows']

        try:
            procedures = vyu.get_procedure_with_name(
                    self.task_name,
                    procedures=available_procedures,
                    workflows=available_workflows)
        except ctrl.DAQConfigError:
            raise ctrl.DAQConfigError(
                    f'No procedure with name: {self.task_name} found')

        dependencies = []
        for i, procedure in enumerate(procedures):
            output_dir = output_directory / procedure['name']
            if not output_directory.exists():
                os.makedirs(output_directory)
            if not output_dir.exists():
                os.makedirs(output_dir)
            task_state = deepcopy(self.system_state)
            task_state['procedure'] = procedure
            dependency_level = self.system_state['dependency_level']
            if procedure['type'] == 'daq':
                dependencies.append(
                    DataField(system_state=task_state,
                              id=self.id,
                              priority=len(procedures) * i * 100 * dependency_level))
            if procedure['type'] == 'analysis':
                dependencies.append(
                    Distillery(system_state=task_state,
                               id=self.id,
                               priority=i * 100 * dependency_level))
        return dependencies

    def run(self):
        in_calib_files = []
        ofiles = self.output()
        for ifiles in self.input():
            in_calib_files.append(ifiles['full-calibration'])
        full_calibration = {}
        for calibfile in in_calib_files:
            with calibfile.open('r') as cf:
                calib = cfu.load_configuration(cf)
                dtu.update_dict(full_calibration, calib, in_place=True)
        with ofiles['full-calibration'].open() as fcf:
            fcf.write(yaml.safe_dump(full_calibration))
