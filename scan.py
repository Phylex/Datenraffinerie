import luigi
from luigi import target
import yaml
from config_utilities import generate_patch_dict_from_key_tuple
from config_utilities import patch_configuration
from pathlib import Path
import os
from time import sleep
from control_adapter import TargetAdapter, DAQAdapter



class Measurement(luigi.Task):
    """
    The task that performs a single measurement for the scan task
    """
    # configuration and connection to the target (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter()
    target_conn = luigi.Parameter()

    # Directory that the data should be stored in
    output_dir = luigi.Parameter()

    # configuration of the (daq) zmq-server
    daq_server_config = luigi.DictParameter()
    daq_server_conn = luigi.Parameter()

    # configuration of the (daq) zmq-client
    daq_client_config = luigi.DictParameter()
    daq_client_conn = luigi.Parameter()

    def output(self):
        """
        Specify the output of this task to be the measured data along with the
        configuration of the target during the measurement
        """
        measurement_config = yaml.dump(self.target_config)
        measurement_hash = f'{abs(hash(measurement_config)):X}'
        self.config_path = Path(self.output_dir) / measurement_hash+'-config.yaml'
        self.data_path = Path(self.output_dir) / measurement_hash+'-data.root'
        return [luigi.LocalTarget(self.config_path),
                luigi.LocalTarget(self.data_path)]

    def run(self):
        """
        Perform the measurement after configuring the different parts
        of the system
        """
        self.daq_server_conn.configure(self.daq_server_config)
        self.target_conn.configure(self.target_config)
        aquire_measurement(self.daq_server_conn)

    def acquire_measurement(self):
        """
        Auxiliary function that acquires a single run of events
        needs the connection to the server to start the acquisition
        """
        self.daq_server_conn.start()
        while not self.daq_server_conn.is_done():
            sleep(0.01)
        self.daq_server_conn.stop()


class scan(luigi.Task):
    """
    A Scan over one parameter or over other scans

    The scan uses the base configuration as the state of the system
    and then modifies it by applying patches constructed from
    parameter/value pairs passed to the scan and then calling either
    the measurement task or a sub-scan with the patched configurations
    as their respective base configurations
    """
    output_dir = luigi.Parameter(significant=True)
    label = luigi.Parameter(significant=True)
    level = luigi.IntParameter(significant=True, default=True)
    incarnation = luigi.IntParameter(significant=True)

    target_config = luigi.DictParameter(significant=True)
    target_conn = luigi.Parameter(significant=False)
    daq_server_config = luigi.DictParameter(significant=False)
    daq_client_config = luigi.DictParameter(significant=False)

    daq_client = luigi.Parameter()
    daq_server = luigi.Parameter()
    scan_parameters = luigi.ListParameter(significant=True)

    def requires(self):
        """
        Determine the measurements that are required for this scan to proceed.

        The Scan class is a recursive task. For every parameter(dimension) that
        is specified by the parameters argument, the scan task requires a
        set of further scans, one per value of the values entry associated with
        the parameter that the current scan is to scan over, essentially
        creating the Cartesian product of all parameters specified.
        """
        required_tasks = []
        values = self.scan_parameters[0][1]
        parameter = self.scan_parameters[0][0]
        if len(self.scan_parameters) > 1:
            for i, value in enumerate(values):
                patch = generate_patch_dict_from_key_tuple(
                            parameter, value)
                subscan_target_config = patch_configuration(self.target_config, patch)
                required_tasks.append(scan(self.output_dir,
                                           self.label,
                                           self.level + 1,
                                           i + self.incarnation * len(values),
                                           subscan_target_config,
                                           self.target_conn,
                                           self.daq_client_config,
                                           self.daq_server_config,
                                           self.daq_client,
                                           self.daq_server,
                                           self.scan_parameters[1:]))
    # configuration and connection to the target (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter()
    target_conn = luigi.Parameter()

    # Directory that the data should be stored in
    output_dir = luigi.Parameter()

    # configuration of the (daq) zmq-server
    daq_server_config = luigi.DictParameter()
    daq_server_conn = luigi.Parameter()

    # configuration of the (daq) zmq-client
    daq_client_config = luigi.DictParameter()
    daq_client_conn = luigi.Parameter()
        else:
            for value in values:
                patch = generate_patch_dict_from_key_tuple(
                        parameter, value)
                measurement_config = patch_configuration(self.base_config,
                                                         patch)
                self.output.append(luigi.LocalTarget(Path(self.output_dir) /
                                   data_fname))
                required_tasks.append(Measurement(measurement_config,
                                                  self.target_
                                                  self.output_dir,
                                                  self.target,
                                                  self.daq_server,
                                                  self.daq_client))
        return required_tasks

    def run(self):
        pass

    def output(self):
        pass
