import luigi
from luigi import target
import yaml
from config_utilities import generate_patch_dict_from_key_tuple
from config_utilities import patch_configuration
from pathlib import Path
import os
from time import sleep
from control_adapter import TargetAdapter, DAQAdapter
from functools import reduce
import operator
import pandas as pd


class Measurement(luigi.Task):
    """
    The task that performs a single measurement for the scan task
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter()
    target_conn = luigi.Parameter()

    # Directory that the data should be stored in
    output_dir = luigi.Parameter()
    label = luigi.Parameter()
    identifier = luigi.IntParameter()


    # configuration of the (daq) system
    daq_system = luigi.Parameter()
    daq_system_config = luigi.DictParameter()

    def output(self):
        """
        Specify the output of this task to be the measured data along with the
        configuration of the target during the measurement
        """
        config_path = Path(self.output_dir) / self.label +\
            str(self.identifier) + '-config.yaml'
        data_path = Path(self.output_dir) / self.label +\
            str(self.identifier) + '-data.raw'
        return [luigi.LocalTarget(config_path),
                luigi.LocalTarget(data_path)]

    def run(self):
        """
        Perform the measurement after configuring the different parts
        of the system
        """
        output_files = self.output()
        config_file = output_files[0]
        data_file = output_files[1]
        self.daq_system.configure(self.daq_system_config)
        self.target_conn.configure(self.target_config)
        with data_file.open('w') as dfile:
            yaml.dump(self.target_config, dfile)
        self.daq_system.acquire_measurement(data_file.path)


class Format(luigi.Task):
    """
    Task that unpacks the raw data into the desired data format
    also merges the yaml chip configuration with the reformatted
    data.
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter(significant=False)
    target_conn = luigi.Parameter(significant=False)

    # Directory that the data should be stored in
    output_dir = luigi.Parameter(significant=False)
    output_format = luigi.Parameter(significant=False)
    label = luigi.Parameter(significant=False)
    identifier = luigi.IntParameter(significant=True)

    # configuration of the (daq) system
    daq_system = luigi.Parameter(significant=False)
    daq_system_config = luigi.DictParameter(significant=False)

    def requires(self):
        """
        to be able to unpack the data we need the data and the
        configuration file. These are returned by the 
        """
        return Measurement(self.target_config,
                           self.target_conn,
                           self.output_dir,
                           self.label,
                           self.identifier,
                           self.daq_system,
                           self.daq_system_config)

    def output(self):
        """
        define the file that is to be produced by the unpacking step
        the identifier is used to make the file unique from the other
        unpacking steps
        """
        formatted_data_path = Path(self.output_dir) / self.label +\
                str(self.identifier) + '.' + self.output_format
        return luigi.LocalTarget(self.output_dir)

    def run(self):
        pass


class Scan(luigi.Task):
    """
    A Scan over one parameter or over other scans

    The scan uses the base configuration as the state of the system
    and then modifies it by applying patches constructed from
    parameter/value pairs passed to the scan and then calling either
    the measurement task or a sub-scan with the patched configurations
    as their respective base configurations
    """
    # parameters describing the position of the parameters in the task
    # tree
    task_id = luigi.parameter(significant=True)

    # parameters describing to the type of measurement being taken
    # and the relevant information for the measurement/scan
    label = luigi.Parameter(significant=False)
    output_dir = luigi.Parameter(significant=False)
    output_format = luigi.Parameter(significant=False)
    scan_parameters = luigi.ListParameter(significant=True)

    # configuration of the target and daq system that is used to
    # perform the scan (This may be extended with an 'environment')
    target_conn = luigi.Parameter(significant=False)
    target_config = luigi.DictParameter(significant=False)
    daq_system = luigi.Parameter(significant=False)
    daq_system_config = luigi.DictParameter(significant=False)

    supported_formats = ['hdf5']

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
        # if there are more than one entry in the parameter list the scan still
        # has more than one dimension. So spawn more scan tasks for the lower
        # dimension
        if len(self.scan_parameters) > 1:
            # calculate the id of the task by multiplication of the length of
            # the dimensions still in the list
            task_id_offset = reduce(operator.mul,
                                    [len(param[1]) for param in
                                     self.scan_parameters[1:]])
            for i, value in enumerate(values):
                patch = generate_patch_dict_from_key_tuple(
                            parameter, value)
                subscan_target_config = patch_configuration(self.target_config,
                                                            patch)
                required_tasks.append(Scan(self.task_id + 1 + task_id_offset
                                           * i,
                                           self.label,
                                           self.output_dir,
                                           self.output_format,
                                           self.scan_parameters[1:],
                                           self.target_conn,
                                           subscan_target_config,
                                           self.daq_system,
                                           self.daq_system_config))
        # The scan has reached the one dimensional case. Spawn a measurement
        # for every value that takes part in the scan
        else:
            for i, value in enumerate(values):
                patch = generate_patch_dict_from_key_tuple(
                        parameter, value)
                measurement_config = patch_configuration(self.base_config,
                                                         patch)
                required_tasks.append(Format(measurement_config,
                                             self.target_conn
                                             self.output_dir,
                                             self.output_format,
                                             self.label,
                                             self.task_id + i
                                             self.daq_system,
                                             self.daq_system_config))
        return required_tasks

    def run(self):
        """
        concatenate the files of a measurement together into a single file
        and write the merged data
        """
        data_segments = []
        for data_file in self.input():
            data_segments.append(pd.read_hdf(file))
        merged_data = pd.concat(data_segments, ignore_index=True, axis=0)
        with self.output().open('wb') as outfile:
            merged_data.to_hdf(outfile)

    def output(self):
        """
        generate the output file for the scan task
        """
        if self.output_format not in self.supported_formats:
            output_path = Path(self.output_dir) /\
                          self.task_id + 'merged.' + self.output_format
        return luigi.LocalTarget(output_path)
