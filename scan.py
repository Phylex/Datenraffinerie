"""
Module containing the classes that together constitute a measurement
and encapsulate the different steps needed to take a measurement using the
hexaboard
"""
from pathlib import Path
from functools import reduce
import os
import operator
import pandas as pd
import luigi
import yaml
import config_utilities as cfu
from control_adapter import DAQSystem, TargetAdapter


class Configuration(luigi.Task):
    """
    Write the configuration file for every run this way the
    configuration can be created without needing to run the
    whole daq process
    """
    target_config = luigi.DictParameter(significant=False)
    label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    identifier = luigi.IntParameter(significant=True)
    calibration = luigi.OptionalParameter(default=None,
                                          significant=False)
    root_config_path = luigi.Parameter(significant=True)

    def requires(self):
        from valve_yard import ValveYard
        # if a calibration is needed then the delegate finding
        # the calibration and adding the subsequent tasks to the
        # to the ValveYard
        if self.calibration is not None:
            return ValveYard(self.root_config_path,
                             self.calibration,
                             str(Path(self.output_dir).resolve()))

    def output(self):
        output_path = Path(self.output_dir) / (self.label +\
            str(self.identifier) + '-config.yaml')
        return luigi.LocalTarget(output_path)

    def run(self):
        target_config = cfu.unfreeze(self.target_config)
        if self.calibration is not None:
            calib_file = self.input()[0].open('r')
            calibration = yaml.safe_load(calib_file)
            out_config = cfu.update_dict(target_config, calibration)
        else:
            out_config = target_config
        with self.output().open('w') as conf_out_file:
            yaml.dump(out_config, conf_out_file)


class Measurement(luigi.Task):
    """
    The task that performs a single measurement for the scan task
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter(significant=False)

    # configuration of the (daq) system
    daq_system_config = luigi.DictParameter(significant=False)

    # Directory that the data should be stored in
    output_dir = luigi.Parameter(significant=True)
    label = luigi.Parameter(significant=True)
    identifier = luigi.IntParameter(significant=True)


    root_config_path = luigi.Parameter(significant=False)

    # calibration if one is required
    calibration = luigi.OptionalParameter(default=None,
                                          significant=False)

    recources = {'hexacontroller': 1}

    def requires(self):
        return Configuration(self.target_config,
                             self.label,
                             self.output_dir,
                             self.identifier,
                             self.calibration,
                             self.root_config_path)

    def output(self):
        """
        Specify the output of this task to be the measured data along with the
        configuration of the target during the measurement
        """
        data_path = Path(self.output_dir) / (self.label +\
            str(self.identifier) + '-data.raw')
        return (luigi.LocalTarget(data_path), self.input())

    def run(self):
        """
        Perform the measurement after configuring the different parts
        of the system
        """

        # load the possibly calibrated configuration from the configuration
        # task
        with self.input().open('r') as config_file:
            target_config = yaml.safe_load(config_file.read())
        daq_system = DAQSystem(cfu.unfreeze(self.daq_system_config))
        target = TargetAdapter(cfu.unfreeze(target_config))
        target.configure()
        data_file = self.output()[0]
        daq_system.take_data(data_file.path)


class Format(luigi.Task):
    """
    Task that unpacks the raw data into the desired data format
    also merges the yaml chip configuration with the reformatted
    data.
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter(significant=False)

    # configuration of the (daq) system
    daq_system_config = luigi.DictParameter(significant=False)

    # Directory that the data should be stored in
    output_dir = luigi.Parameter(significant=True)
    output_format = luigi.Parameter(significant=False)
    label = luigi.Parameter(significant=True)
    identifier = luigi.IntParameter(significant=True)


    root_config_path = luigi.Parameter(significant=False)
    # calibration if one is required
    calibration = luigi.Parameter(significant=False)

    def requires(self):
        """
        to be able to unpack the data we need the data and the
        configuration file. These are returned by the 
        """
        return Measurement(self.target_config,
                           self.daq_system_config,
                           self.output_dir,
                           self.label,
                           self.identifier,
                           self.root_config_path,
                           self.calibration)

    def output(self):
        """
        define the file that is to be produced by the unpacking step
        the identifier is used to make the file unique from the other
        unpacking steps
        """
        formatted_data_path = Path(self.output_dir) / \
            (self.label + str(self.identifier) + '.' + self.output_format)
        return luigi.LocalTarget(formatted_data_path.resolve())

    def run(self):
        data_file_path = Path(self.input()[0].path).resolve()
        unpack_command = 'unpack'
        input_file = '-i ' + str(data_file_path)
        output_file = os.path.splitext(data_file_path)[0] + '.root'
        output_command = '-o ' + output_file
        full_unpack_command = unpack_command + input_file + output_command
        print(full_unpack_command)
        # os.system(full_unpack_command)


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
    identifier = luigi.IntParameter(significant=True)

    # parameters describing to the type of measurement being taken
    # and the relevant information for the measurement/scan
    label = luigi.Parameter(significant=False)
    output_dir = luigi.Parameter(significant=False)
    output_format = luigi.Parameter(significant=False)
    scan_parameters = luigi.ListParameter(significant=True)

    # configuration of the target and daq system that is used to
    # perform the scan (This may be extended with an 'environment')
    target_config = luigi.DictParameter(significant=False)
    daq_system_config = luigi.DictParameter(significant=False)

    root_config_path = luigi.Parameter(significant=True)
    # calibration if one is required
    calibration = luigi.OptionalParameter(significant=False,
                                          default=None)

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
        parameter = list(self.scan_parameters[0][0])
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
                patch = cfu.generate_patch(
                            parameter, value)
                subscan_target_config = cfu.update_dict(
                        self.target_config,
                        patch)
                required_tasks.append(Scan(self.identifier + 1 + task_id_offset
                                           * i,
                                           self.label,
                                           self.output_dir,
                                           self.output_format,
                                           self.scan_parameters[1:],
                                           subscan_target_config,
                                           self.daq_system_config,
                                           self.root_config_path,
                                           self.calibration))
        # The scan has reached the one dimensional case. Spawn a measurement
        # for every value that takes part in the scan
        else:
            for i, value in enumerate(values):
                patch = cfu.generate_patch(parameter, value)
                measurement_config = cfu.patch_configuration(
                        self.target_config,
                        patch)
                required_tasks.append(Format(measurement_config,
                                             self.daq_system_config,
                                             self.output_dir,
                                             self.output_format,
                                             self.label,
                                             self.identifier + i,
                                             self.root_config_path,
                                             self.calibration))
        return required_tasks

    def run(self):
        """
        concatenate the files of a measurement together into a single file
        and write the merged data
        """
        data_segments = []
        for data_file in self.input():
            data_segments.append(pd.read_hdf(data_file))
        merged_data = pd.concat(data_segments, ignore_index=True, axis=0)
        with self.output().open('wb') as outfile:
            merged_data.to_hdf(outfile)

    def output(self):
        """
        generate the output file for the scan task
        """
        if self.output_format in self.supported_formats:
            out_file = str(self.identifier) + 'merged.' + self.output_format
            output_path = Path(self.output_dir) / out_file
            return luigi.LocalTarget(output_path)
        raise KeyError("The output format for the scans needs to"
                       " one of the following:\n"
                       f"{self.supported_formats}")
