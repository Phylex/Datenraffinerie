import luigi
from luigi import target
import yaml
from config_utilities import generate_patch_dict_from_key_tuple
from config_utilities import patch_configuration
from pathlib import Path
import os

class Measurement(luigi.Task):
    config = luigi.DictParameter()
    output_dir = luigi.Parameter()
    target = luigi.Parameter()
    daq_server = luigi.Parameter()
    daq_client = luigi.Parameter()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        measurement_config = yaml.dump(self.config)
        measurement_hash = f'{abs(hash(measurement_config)):X}'
        self.config_path = Path(self.output_dir) / measurement_hash+'-config.yaml'
        self.data_path = Path(self.output_dir) / measurement_hash+'-config.yaml'


    def output(self):
        return [luigi.LocalTarget(self.config_path),
                luigi.LocalTarget(self.data_path)]

    def run(self):
        daq_client_config = self.config['daq_client']
        daq_server_congig = self.config['daq_server']
        target_config = self.config['target']
        self.daq_server.configure(daq_server_congig)
        self.daq_client.configure(daq_client_config)
        self.target.configure(target_config)
        self.daq_client.aquire(self.output()[1].path)


class scan(luigi.Task):
    """
    A Scan over one parameter

    The scan uses the base configuration as the state of the system
    and then modifies the 
    """
    priority = luigi.IntParameter()
    base_config = luigi.DictParameter(significant=True)
    environment = luigi.DictParameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    parameters = luigi.DictParameter()
    values = luigi.ListParameter()
    daq_server = luigi.Parameter()
    daq_client = luigi.Parameter()
    target = luigi.Parameter()
    First = luigi.Parameter()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.parameters) > 1:
            self.higher_order = True
        else:
            self.higher_order = False
        self.output = []

    def requires(self):
        required_tasks = []
        if self.higher_order:
            for value in self.values[0]:
                patch = generate_patch_dict_from_key_tuple(
                            self.parameters[0], value)
                subscan_config = patch_configuration(self.base_config, patch)
                required_tasks.append(scan(0, subscan_config, self.environment,
                                           self.output_dir,
                                           self.parameters[1:],
                                           self.values[1:],
                                           self.daq_server,
                                           self.daq_client,
                                           self.target,
                                           False)
                                      )
        else:
            for value in self.values[0]:
                patch = generate_patch_dict_from_key_tuple(
                        self.parameters[0], value)
                measurement_config = patch_configuration(self.base_config,
                                                         patch)
                self.output.append(luigi.LocalTarget(Path(self.output_dir) /
                                   data_fname))
                required_tasks.appen(Measurement(measurement_config,
                                                 self.output_dir,
                                                 self.target,
                                                 self.daq_server,
                                                 self.daq_client))

        return required_tasks


    def run(self):
        if self.First:
            self.daq_server.init()
            self.daq_client.init()
            self.target.init()
        if not self.higher_order:
        else:
            


    def output(self):
        if len(self.parameters > 1):

        return self.output
