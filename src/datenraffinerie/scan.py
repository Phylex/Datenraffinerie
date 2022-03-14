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
from luigi.parameter import ParameterVisibility
import subprocess
import yaml
import zmq
from uproot.exceptions import KeyInFileError
from . import config_utilities as cfu
from . import analysis_utilities as anu


class Calibration(luigi.Task):
    """
    fetches the Calibration for a daq procedure this is normally
    done by the
    """
    root_config_path = luigi.Parameter()
    calibration = luigi.Parameter()
    output_dir = luigi.Parameter()
    analysis_module_path = luigi.Parameter()
    loop = luigi.BoolParameter()

    def requires(self):
        from .valve_yard import ValveYard
        # if a calibration is needed then the delegate finding
        # the calibration and adding the subsequent tasks to the
        # to the ValveYard
        if self.calibration is not None:
            return ValveYard(self.root_config_path,
                             self.calibration,
                             os.path.dirname(str(Path(self.output_dir).resolve())),
                             str(Path(self.analysis_module_path).resolve()),
                             self.loop)

    def output(self):
        local_calib_path = Path(self.output_dir) / 'calibration.yaml'
        return luigi.LocalTarget(local_calib_path)

    def run(self):
        # figure out if there is a calibration that we need and if so create a
        # local copy so that we don't end up calling the valve yard multiple times
        if self.calibration is not None:
            with self.input()['calibration'].open('r') as calibration_file:
                with self.output().open('w') as local_calib_copy:
                    local_calib_copy.write(calibration_file.read())
        else:
            with self.output().open('w') as local_calib_copy:
                local_calib_copy.write('')


class DrillingRig(luigi.Task):
    """
    Task that unpacks the raw data into the desired data format
    also merges the yaml chip configuration with the reformatted
    data.
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    target_config = luigi.DictParameter(significant=False)
    target_default_config = luigi.DictParameter(significant=False)

    # configuration of the (daq) system
    daq_system_config = luigi.DictParameter(significant=False)

    # Directory that the data should be stored in
    output_dir = luigi.Parameter(significant=True)
    output_format = luigi.Parameter(significant=False)
    label = luigi.Parameter(significant=True)
    identifier = luigi.IntParameter(significant=True)

    # the path to the root config file so that the Configuration
    # task can call the valveyard if a calibration is required
    root_config_path = luigi.Parameter(True)
    # calibration if one is required
    calibration = luigi.OptionalParameter(significant=False)
    analysis_module_path = luigi.OptionalParameter(significant=False)
    network_config = luigi.DictParameter(significant=True)
    loop = luigi.BoolParameter(significant=False)
    raw = luigi.BoolParameter(significant=True)
    data_columns = luigi.ListParameter(significant=False)

    def requires(self):
        return Calibration(self.root_config_path,
                           self.calibration,
                           self.output_dir,
                           self.analysis_module_path,
                           self.loop)

    def output(self):
        """
        define the file that is to be produced by the unpacking step
        the identifier is used to make the file unique from the other
        unpacking steps
        """
        formatted_data_path = Path(self.output_dir) / \
            f'{self.label}_{self.identifier}.{self.output_format}'
        return luigi.LocalTarget(formatted_data_path.resolve())

    def run(self):
        # load the configurations
        target_config = cfu.unfreeze(self.target_config)
        daq_system_config = cfu.unfreeze(self.daq_system_config)
        power_on_default = cfu.unfreeze(self.target_default_config)

        # load the calibration
        if self.calibration is not None:
            with self.input().open('r') as calibration_file:
                calibration = yaml.safe_load(
                    calibration_file.read())
            # calculate the configuration to send to the backend
            target_config = cfu.update_dict(target_config,
                                            calibration)

        target_config = cfu.diff_dict(power_on_default,
                                      target_config)
        full_target_config = cfu.update_dict(power_on_default,
                                             target_config)
        complete_config = {'daq': daq_system_config,
                           'target': full_target_config}

        # create the config on disk
        output_config = os.path.splitext(self.output().path)[0] + '.yaml'
        config_string = yaml.safe_dump(complete_config)
        with open(output_config, 'w') as run_config:
            run_config.write(config_string)

        # send config to the backend and wait for the response
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(
                f"tcp://{self.network_config['daq_coordinator']['hostname']}:" +
                f"{self.network_config['daq_coordinator']['port']}")
        socket.send_string('measure;' + config_string)
        data = socket.recv()
        socket.close()
        context.term()
        raw_data_file_path = os.path.splitext(self.output().path)[0] + '.raw'

        # save the data in a file so that the unpacker can work with it
        with open(raw_data_file_path, 'wb') as raw_data_file:
            raw_data_file.write(data)

        data_file_path = os.path.splitext(self.output().path)[0] + '.root'

        result = anu.unpack_raw_data_into_root(raw_data_file_path,
                                  data_file_path,
                                  raw_data=self.raw)
        if result != 0:
            os.remove(raw_data_file_path)
            os.remove(data_file_path)
            raise ValueError(f"The unpacker failed for {raw_data_file_path}")

        # load the data from the unpacked root file and merge in the
        # data from the configuration for that run with the data
        output_path = Path(self.output().path)
        anu.reformat_data(data_file_path, output_path, complete_config, self.raw,
                          columns=self.data_columns)
        os.remove(data_file_path)


class DataField(luigi.Task):
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
    label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    output_format = luigi.Parameter(significant=False)
    scan_parameters = luigi.ListParameter(significant=False)

    # configuration of the target and daq system that is used to
    # perform the scan (This may be extended with an 'environment')
    target_config = luigi.DictParameter(significant=False)
    target_default_config = luigi.DictParameter(significant=False)
    daq_system_config = luigi.DictParameter(significant=False)

    root_config_path = luigi.Parameter(significant=True)
    # calibration if one is required
    calibration = luigi.OptionalParameter(significant=False,
                                          default=None)
    analysis_module_path = luigi.OptionalParameter(significant=False,
                                                   default=None)
    network_config = luigi.DictParameter(significant=False)
    loop = luigi.BoolParameter(significant=False)
    raw = luigi.BoolParameter(significant=False)
    data_columns = luigi.ListParameter(significant=False)

    supported_formats = ['hdf5']

    @property
    def priority(self):
        if self.loop and len(self.scan_parameters) == 1:
            return 10
        return 0

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
        target_config = cfu.unfreeze(self.target_config)
        daq_system_config = cfu.unfreeze(self.daq_system_config)
        complete_config = {'target': target_config,
                           'daq': daq_system_config}

        # if there are more than one entry in the parameter list the scan still
        # has more than one dimension. So spawn more scan tasks for the lower
        # dimension
        if len(self.scan_parameters) > 1:
            # calculate the id of the task by multiplication of the length of
            # the dimensions still in the list
            task_id_offset = reduce(operator.mul,
                                    [len(param[1]) for param in
                                     self.scan_parameters[1:]])
            subscan_target_config = target_config
            subscan_daq_config = daq_system_config
            for i, value in enumerate(values):

                if type(value)==tuple:
                    value=list(value)

                patch = cfu.generate_patch(
                            parameter, value)
                complete_subscan_config = cfu.update_dict(complete_config, patch)
                subscan_daq_config = complete_subscan_config['daq']
                subscan_target_config = complete_subscan_config['target']
                if len(self.scan_parameters[1:]) == 1 and self.loop:
                    required_tasks.append(Fracker(self.identifier + 1 + task_id_offset * i,
                                                  self.label,
                                                  self.output_dir,
                                                  self.output_format,
                                                  self.scan_parameters[1:],
                                                  subscan_target_config,
                                                  self.target_default_config,
                                                  subscan_daq_config,
                                                  self.root_config_path,
                                                  self.calibration,
                                                  self.analysis_module_path,
                                                  self.network_config,
                                                  self.loop,
                                                  self.raw,
                                                  self.data_columns))
                else:
                    required_tasks.append(DataField(self.identifier + 1 + task_id_offset * i,
                                                    self.label,
                                                    self.output_dir,
                                                    self.output_format,
                                                    self.scan_parameters[1:],
                                                    subscan_target_config,
                                                    self.target_default_config,
                                                    subscan_daq_config,
                                                    self.root_config_path,
                                                    self.calibration,
                                                    self.analysis_module_path,
                                                    self.network_config,
                                                    self.loop,
                                                    self.raw,
                                                    self.data_columns))
        # The scan has reached the one dimensional case. Spawn a measurement
        # for every value that takes part in the scan
        else:
            if self.loop:
                return Calibration(self.root_config_path,
                                   self.calibration,
                                   self.output_dir,
                                   self.analysis_module_path,
                                   self.loop)

            for i, value in enumerate(values):
                patch = cfu.generate_patch(parameter, value)
                complete_config = cfu.update_dict(complete_config, patch)
                measurement_daq_config = complete_config['daq']
                measurement_target_config = complete_config['target']
                required_tasks.append(DrillingRig(measurement_target_config,
                                                  self.target_default_config,
                                                  measurement_daq_config,
                                                  self.output_dir,
                                                  self.output_format,
                                                  self.label,
                                                  self.identifier + i,
                                                  self.root_config_path,
                                                  self.calibration,
                                                  self.analysis_module_path,
                                                  self.network_config,
                                                  self.loop,
                                                  self.raw,
                                                  self.data_columns))
        return required_tasks

    def output(self):
        """
        generate the output file for the scan task

        If we are in the situation of being called by the fracker (first if condition)
        it is the job of the DataField to simply produce the raw files. It then also needs
        to figure out what files still need to be generated, as such it needs check what
        files have already been converted by the fracker. The fracker will fail and stall
        the rest of the luigi pipeline if it can't unpack the file. The user then needs to
        rerun the datenraffinerie
        """
        # we are being called by the fracker, so only produce the raw output files
        if len(self.scan_parameters) == 1 and self.loop:
            raw_files = []
            # pass the calibrated default config to the fracker
            raw_files.append(self.input())
            values = self.scan_parameters[0][1]
            for i, value in enumerate(values):
                base_file_name = f'{self.label}_{self.identifier + i}'
                raw_file_name = f'{base_file_name}.raw'
                fracked_file_name = f'{base_file_name}.hdf5'
                fracked_file_path = Path(self.output_dir) / fracked_file_name
                # if there already is a converted file we do not need to
                # acquire the data again
                if fracked_file_path.exists():
                    continue
                raw_file_path = Path(self.output_dir) / raw_file_name
                raw_files.append(luigi.LocalTarget(raw_file_path,
                                                   format=luigi.format.Nop))
            return raw_files

        # this task is not required by the fracker so we do the usual merge job
        if self.output_format in self.supported_formats:
            out_file = f'{self.label}_{self.identifier}_merged.{self.output_format}'
            raw_file_path = Path(self.output_dir) / out_file
            return luigi.LocalTarget(raw_file_path)
        raise KeyError("The output format for the scans needs to"
                       " one of the following:\n"
                       f"{self.supported_formats}")

    def run(self):
        """
        concatenate the files of a measurement together into a single file
        and write the merged data, or if the 'loop' parameter is set, it performs
        the measurements and lets the fracker handle the initial conversion into
        usable files if loop is set the fracker also does the merging at the
        end so in that case it is really 'just' there to acquire the data'.
        """

        # the fracker required us so we acquire the data and don't do any
        # further processing
        if self.loop and len(self.scan_parameters) == 1:
            # open the socket to the daq coordinator
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(
                f"tcp://{self.network_config['daq_coordinator']['hostname']}:"
                f"{self.network_config['daq_coordinator']['port']}")

            target_config = cfu.unfreeze(self.target_config)
            daq_system_config = cfu.unfreeze(self.daq_system_config)
            power_on_default = cfu.unfreeze(self.target_default_config)
            # load the calibration
            if self.calibration is not None:
                with self.input().open('r') as calibration_file:
                    calibration = yaml.safe_load(
                        calibration_file.read())
                # calculate the configuration to send to the backend
                target_config = cfu.update_dict(target_config, calibration)

            target_config = cfu.diff_dict(power_on_default,
                                          target_config)
            complete_config = {'daq': daq_system_config,
                               'target': target_config}

            # perform the scan
            values = self.scan_parameters[0][1]
            parameter = list(self.scan_parameters[0][0])
            output_files = self.output()[1:]
            output_configs = [os.path.splitext(of.path)[0] + '.yaml'
                              for of in output_files]
            for raw_file, output_config, value in\
                    zip(output_files, output_configs, values):
                if Path(raw_file.path).exists():
                    continue
                # patch the target config with the key for the current run
                # luigi might have converted an input list to a tuple
                if isinstance(value, tuple):
                    value = list(value)

                # generate the run configuration and write it to a file
                patch = cfu.generate_patch(parameter, value)
                complete_config = cfu.update_dict(complete_config, patch)
                with open(output_config, 'w') as run_config:
                    run_config.write(yaml.safe_dump(complete_config))

                # send the measurement command to the backend starting the
                # measurement
                socket.send_string('measure;'+yaml.safe_dump(complete_config))
                # wait for the data to return
                data = socket.recv()

                # save the data in a file so that the unpacker can work with it
                with raw_file.open('w') as raw_data_file:
                    raw_data_file.write(data)

            # close the connection to the daq coordinator
            # as the scan is now complete
            socket.close()
            context.term()

        # the measurements are being performed in the Measurement tasks
        # so the inputs are already unpacked hdf5 files and output is
        # the single merged file
        else:
            in_files = [data_file.path for data_file in self.input()]
            # merge the data together
            anu.merge_files(in_files, self.output().path, self.raw)


class Fracker(luigi.Task):
    """
    convert the format of the raw data into something that can be
    used by the distilleries
    """
    # parameters describing the position of the parameters in the task
    # tree
    identifier = luigi.IntParameter(significant=True)

    # parameters describing to the type of measurement being taken
    # and the relevant information for the measurement/scan
    label = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    output_format = luigi.Parameter(significant=False)
    scan_parameters = luigi.ListParameter(significant=False)

    # configuration of the target and daq system that is used to
    # perform the scan (This may be extended with an 'environment')
    target_config = luigi.DictParameter(significant=False)
    target_default_config = luigi.DictParameter(significant=False)
    daq_system_config = luigi.DictParameter(significant=False)

    root_config_path = luigi.Parameter(significant=True)
    # calibration if one is required
    calibration = luigi.OptionalParameter(significant=False,
                                          default=None)
    analysis_module_path = luigi.OptionalParameter(significant=False,
                                                   default=None)
    network_config = luigi.DictParameter(significant=False)
    loop = luigi.BoolParameter(significant=False)
    raw = luigi.BoolParameter(significant=False)
    data_columns = luigi.ListParameter(significant=False)
    supported_formats = ['hdf5']

    def requires(self):
        return DataField(identifier=self.identifier,
                         label=self.label,
                         output_dir=self.output_dir,
                         output_format=self.output_format,
                         scan_parameters=self.scan_parameters,
                         target_config=self.target_config,
                         target_default_config=self.target_default_config,
                         daq_system_config=self.daq_system_config,
                         root_config_path=self.root_config_path,
                         calibration=self.calibration,
                         analysis_module_path=self.analysis_module_path,
                         network_config=self.network_config,
                         loop=self.loop,
                         raw=self.raw,
                         data_columns=self.data_columns)

    def output(self):
        """
        generate the output file for the scan task
        """
        if self.output_format in self.supported_formats:
            out_file = str(self.identifier) + '_merged.' + self.output_format
            output_path = Path(self.output_dir) / out_file
            return luigi.LocalTarget(output_path)
        raise KeyError("The output format for the scans needs to"
                       " one of the following:\n"
                       f"{self.supported_formats}")

    def run(self):
        # load the configurations
        target_config = cfu.unfreeze(self.target_config)
        daq_config = cfu.unfreeze(self.daq_system_config)
        power_on_default = cfu.unfreeze(self.target_default_config)
        # load the calibration
        if self.calibration is not None:
            with self.input()[0].open('r') as calibration_file:
                calibration = yaml.safe_load(
                    calibration_file.read())
            # calculate the configuration to send to the backend
            target_config = cfu.update_dict(target_config,
                                            calibration)

        target_config = cfu.update_dict(power_on_default,
                                        target_config)
        complete_config = {'daq': daq_config,
                           'target': target_config}

        for i, raw_file in enumerate(self.input()[1:]):
            data_file_base_name = os.path.splitext(raw_file.path)[0]
            unpacked_file_path = data_file_base_name + '.root'

            result = anu.unpack_raw_data_into_root(
                    raw_file.path,
                    unpacked_file_path,
                    raw_data=self.raw)
            if result != 0:
                os.remove(unpacked_file_path)

        # get the parameters to build the patch from
        values = self.scan_parameters[0][1]
        parameter = list(self.scan_parameters[0][0])
        expected_files = []
        for raw_file, value in zip(self.input()[1:], values):
            data_file_base_name = os.path.splitext(raw_file.path)[0]
            unpacked_file_path = Path(data_file_base_name + '.root')
            formatted_data_path = Path(data_file_base_name + '.hdf5')
            expected_files.append(formatted_data_path)
            # check that the unpacker was able to convert the data into root
            # format
            if not unpacked_file_path.exists():
                os.remove(raw_file.path)
                continue

            # load the data from the unpacked root file and merge in the
            # data from the configuration for that run with the data
            try:
                # calculate the patch that needs to be applied
                patch = cfu.generate_patch(parameter, value)
                complete_config = cfu.update_dict(complete_config, patch)
                anu.reformat_data(unpacked_file_path,
                                  formatted_data_path,
                                  complete_config,
                                  self.raw,
                                  columns=self.data_columns)
            except KeyInFileError:
                os.remove(unpacked_file_path.as_posix())
                continue
            except FileNotFoundError:
                continue
            os.remove(unpacked_file_path.as_posix())

        for formatted_file_path in expected_files:
            if not formatted_file_path.exists():
                raise ValueError('An unpacker failed, '
                                 'the datenraffinerie needs to be rerun')
        anu.merge_files(expected_files, self.output().path)
