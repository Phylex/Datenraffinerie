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
from scan import Scan
import config_utilities as cfu
import control_adapter as ctrl


class ValveYard(luigi.WrapperTask):
    root_config_file = luigi.Parameter(significant=True)
    procedure_label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)

    def requires(self):
        data_dir = Path(self.output_dir)
        if not data_dir.exists():
            os.makedirs(data_dir)
        output_dir = data_dir
        procedures, workflows = cfu.parse_config_file(self.root_config_file)
        procedure_names = list(map(lambda p: p['name'], procedures))
        if self.procedure_label in procedure_names:
            procedure_index = procedure_names.index(self.procedure_label)
        else:
            raise ctrl.DAQConfigError(f"No '{self.procedure_label}' found in"
                                      " the config files")
        procedure = procedures[procedure_index]
        if procedure['type'] == 'analysis':
            raise NotImplementedError('starting analyses from the ValveYard'
                                      ' has has not been implemented yet')
        if procedure['type'] == 'daq':
            return Scan(identifier=0,
                        label=self.procedure_label,
                        output_dir=str(output_dir.resolve()),
                        output_format='root',
                        scan_parameters=procedure['parameters'],
                        target_config=procedure['target_init_config'],
                        target_default_config=procedure['target_power_on_default_config'],
                        daq_system_config=procedure['daq_system_config'],
                        root_config_path=str(
                            Path(self.root_config_file).resolve()),
                        calibration=procedure['calibration'])
        raise cfu.ConfigFormatError("The type of an entry must be either "
                                    "'daq' or 'analysis'")
