import luigi
from scan import Scan
import config_utilities as cfu
import control_adapter as ctrl

class ValveYard(luigi.WrapperTask):
    root_config_file = luigi.Parameter(significant=True)
    procedure_label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)

    def requires(self):
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
        elif procedure['type'] == 'daq':
            daq_system = ctrl.DAQSystem(procedure['daq_system_config'])
            target_system = ctrl.TargetAdapter(
                    procedure['target_power_on_default_config'],
                    procedure['target_init_config'])
            target_config_initialized = cfu.update_dict(
                    procedure['target_power_on_default_config'],
                    procedure['target_init_config'])
            return Scan(task_id=0,
                        label=self.procedure_label,
                        output_dir=self.output_dir,
                        output_format='hdf5',
                        scan_parameters=procedure['parameters'],
                        target_conn=target_system,
                        target_config=target_config_initialized,
                        daq_system=daq_system,
                        daq_system_config=procedure['daq_system_config'],
                        calibration=procedure['calibration'])
