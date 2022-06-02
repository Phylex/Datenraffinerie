"""
Module containing the classes that together constitute a measurement
and encapsulate the different steps needed to take a measurement using the
hexaboard
"""
from pathlib import Path
from functools import reduce
import os
import operator
import shutil
import luigi
import yaml
import zmq
from uproot.exceptions import KeyInFileError
from . import config_utilities as cfu
from . import analysis_utilities as anu
from .errors import DAQConfigError, DAQError
from copy import deepcopy


class Calibration(luigi.Task):
    """
    The calibration task manages the possibility of the initial state of the
    procedure to be calibrated by a previous procedure
    """
    system_state = luigi.DictParameter()

    def requires(self):
        from .valve_yard import ValveYard
        # if a calibration is needed then the delegate finding
        # the calibration and adding the subsequent tasks to the
        # to the ValveYard
        if 'calibration' in self.system_state['procedure']\
                and self.system_state['procedure']['calibration'] is not None:
            child_state = deepcopy(self.system_state)
            del child_state['procedure']
            child_state['name'] = self.system_state['procedure']['calibration']
            return ValveYard(child_state)

    def output(self):
        output_dir = self.system_state['ouptut_path']
        local_calib_path = Path(output_dir) / 'calibration.yaml'
        return {'full-calibration': luigi.LocalTarget(local_calib_path)}

    def run(self):
        # figure out if there is a calibration that we need and if so create a
        # local copy so that we don't end up calling the valve yard multiple
        # times
        if 'full-calibration' in self.input():
            full_calibration = yaml.safe_load(
                    self.input()['full-calibration'].read())
        else:
            full_calibration = {}
        if 'calibration' in self.system_state['procedure'] and\
           self.system_state['procedure']['calibration'] is not None:
            with self.input()['calibration'].open('r') as calibration_file:
                with self.output().open('w') as local_calib_copy:
                    calibration = cfu.patch_configuration(
                            full_calibration,
                            yaml.safe_load(calibration_file.read()))
                    local_calib_copy.write(yaml.safe_dump(calibration))

        else:
            with self.output().open('w') as local_calib_copy:
                local_calib_copy.write(yaml.safe_dump(full_calibration))


class FieldPreparation(luigi.Task):
    """
    Initialize (or re-initialize) the chips to the power-on default
    """
    system_state = luigi.DictParameter()

    def requires(self):
        return Calibration(self.system_state)

    def output(self):
        return self.input()

    def complete(self):
        return self.initialized_to_default

    def run(self):
        # the default values for the DAQ system and the target need to
        # be loaded on to the backend only once
        network_config = self.system_state['network_config']
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(
            f"tcp://{network_config['daq_coordinator']['hostname']}:"
            f"{network_config['daq_coordinator']['port']}")
        target_default_config = self.system_state[
                'produce'][
                'target_settings'][
                'power_on_default']
        daq_default_config = self.system_state[
                'procedure'][
                'daq_settings'][
                'default']
        complete_default_config = {
            'daq': cfu.unfreeze(daq_default_config),
            'target': cfu.unfreeze(target_default_config)}
        socket.send_string('load defaults;' +
                           yaml.safe_dump(complete_default_config))
        socket.setsockopt(zmq.RCVTIMEO, 20000)
        try:
            resp = socket.recv()
        except zmq.error.Again as e:
            raise RuntimeError("Socket is not responding. Please check that "
                               "client and server apps are running, "
                               "and that your network configuration "
                               "is correct") from e
        else:
            if resp != b'defaults loaded':
                raise DAQConfigError('Default config could not be loaded into'
                                     ' the backend')

            self.initialized_to_default = True


class DrillingRig(luigi.Task):
    """
    Task that unpacks the raw data into the desired data format
    also merges the yaml chip configuration with the reformatted
    data.
    """
    # configuration and connection to the target
    # (aka hexaboard/SingleROC tester)
    system_state = luigi.DictParameter(significant=True)
    id = luigi.IntParameter(significant=True)

    def requires(self):
        return FieldPreparation(self.system_state)

    def output(self):
        """
        define the file that is to be produced by the unpacking step
        the identifier is used to make the file unique from the other
        unpacking steps
        """
        output_dir = self.system_state['output_path']
        name = self.system_state['name']
        formatted_data_path = Path(output_dir) / \
            f'{name}_{self.id}.h5'
        out_struct = self.input()
        out_struct['data'] = luigi.LocalTarget(formatted_data_path.resolve())
        return out_struct

    def run(self):
        # load the configurations
        try:
            calibration = yaml.safe_load(
                    self.input()['full-calibration'].read())
        except KeyError:
            calibration = {}

        complete_config = cfu.generate_run_config(self.system_state,
                                                  calibration)
        network_config = self.system_state['network_config']

        # create the config on disk
        output_config = os.path.splitext(self.output()['data'].path)[0]\
            + '.yaml'
        config_string = yaml.safe_dump(complete_config)
        with open(output_config, 'w') as run_config:
            run_config.write(config_string)

        # send config to the backend and wait for the response
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(
                f"tcp://{network_config['daq_coordinator']['hostname']}:"
                f"{network_config['daq_coordinator']['port']}")
        socket.send_string('measure;' + config_string)
        data = socket.recv()
        socket.close()
        context.term()
        base_path = os.path.splitext(self.output()['data'].path)[0]
        raw_data_file_path = base_path + '.raw'
        unpacked_file_path = base_path + '.root'
        # save the data in a file so that the unpacker can work with it
        with open(raw_data_file_path, 'wb') as raw_data_file:
            raw_data_file.write(data)

        # merge in the configuration into the raw data
        # if the fracker can be found run it

        event_mode = self.system_state['event_mode']
        result = anu.unpack_raw_data_into_root(raw_data_file_path,
                                               unpacked_file_path,
                                               raw_data=event_mode)
        if result != 0:
            os.remove(raw_data_file_path)
            if os.path.exists(unpacked_file_path):
                os.remove(unpacked_file_path)
            raise ValueError(f"The unpacker failed for {raw_data_file_path}")

        # load the data from the unpacked root file and merge in the
        # data from the configuration for that run with the data
        formatted_data_path = Path(self.output()['data'].path)
        if shutil.which('fracker') is not None:
            retval = anu.run_compiled_fracker(
                    unpacked_file_path,
                    formatted_data_path,
                    complete_config,
                    event_mode,
                    self.system_state['procedure']['data_columns'])
            if retval != 0:
                print("The fracker failed!!!")
                if formatted_data_path.exists():
                    os.remove(formatted_data_path)
        # otherwise fall back to the python code
        else:
            try:
                anu.reformat_data(unpacked_file_path,
                                  formatted_data_path,
                                  complete_config,
                                  event_mode,
                                  columns=self.system_state[
                                      'procedure'][
                                      'data_columns'])
            except KeyInFileError:
                os.remove(unpacked_file_path)
                os.remove(raw_data_file_path)
                return
            except FileNotFoundError:
                return
        os.remove(unpacked_file_path)


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
    system_state = luigi.DictParameter(significant=True)
    id = luigi.IntParameter(significant=True)
    priority = luigi.OptionalParameter(significant=False, default=0)

    def requires(self):
        """
        Determine the measurements that are required for this scan to proceed.

        The Scan class is a recursive task. For every parameter(dimension) that
        is specified by the parameters argument, the scan task requires a
        set of further scans, one per value of the values entry associated with
        the parameter that the current scan is to scan over, essentially
        creating the Cartesian product of all parameters specified.
        """
        subtasks = []
        scan_parameters = self.system_state['procedure']['parameters']

        # if there are more than one entry in the parameter list the scan still
        # has more than one dimension. So spawn more scan tasks for the lower
        # dimension
        if len(scan_parameters) > 1:
            # calculate the id of the task by multiplication of the length of
            # the dimensions still in the list
            task_id_offset = reduce(operator.mul,
                                    map(lambda x: len(x[1]),
                                        scan_parameters[1:]))
            for i, state in enumerate(
                    cfu.generate_subsystem_states(self.system_state)):
                subtask_id = self.id + 1 + task_id_offset * i
                if len(self.scan_parameters[1:]) == 1 and self.loop:
                    subtasks.append(Fracker(id=subtask_id,
                                            system_state=state))
                else:
                    subtasks.append(DataField(id=subtask_id,
                                              system_state=state))
        # The scan has reached the one dimensional case. Spawn a measurement
        # for every value that takes part in the scan
        else:
            if self.loop:
                return FieldPreparation(self.system_state)
            else:
                for i, state in enumerate(
                        cfu.generate_subsystem_states(self.system_state)):
                    subtasks.append(DrillingRig(id=self.id + i,
                                                system_state=state))
        return subtasks

    def output(self):
        """
        generate the output file for the scan task

        If we are in the situation of being called by the Fracker
        (first if condition) it is the job of the DataField to simply produce
        the raw files. It then also needs to figure out what files still need
        to be generated, as such it needs check what files have already been
        converted by the fracker. The fracker will fail and stall the rest of
        the luigi pipeline if it can't unpack the file. The user then needs to
        rerun the datenraffinerie
        """
        loop = self.system_state['loop']
        scan_parameters = self.system_state['procedure']['parameters']
        name = self.system_state['name']
        output_dir = self.system_state['output_path']
        output_files = {}
        output_files['full-calibration'] = self.input()['full-calibration']
        # we are being called by the fracker, so only produce the raw output
        # files
        if len(scan_parameters) == 1 and loop:
            # pass the calibrated default config to the fracker
            values = self.scan_parameters[0][1]
            raw_files = []
            for i, value in enumerate(values):
                base_file_name = f'{name}_{self.id + i}'
                raw_file_name = f'{base_file_name}.raw'
                # if there already is a converted file we do not need to
                # acquire the data again
                raw_file_path = Path(self.output_dir) / raw_file_name
                raw_files.append(luigi.LocalTarget(raw_file_path,
                                                   format=luigi.format.Nop))
            output_files['data'] = raw_files
            return output_files

        # this task is not required by the fracker so we do the usual merge job
        elif not self.system_state['event_mode']:
            out_file = f'{name}_{self.id}_merged.h5'
            merged_file_path = Path(output_dir) / out_file
            output_files['data'] = luigi.LocalTarget(merged_file_path)
            return output_files
        # if we are running in raw mode do not concatenate the files together
        else:
            return output_files

    def run(self):
        """
        concatenate the files of a measurement together into a single file
        and write the merged data, or if the 'loop' parameter is set, it
        performs the measurements and lets the fracker handle the initial
        conversion into usable files if loop is set the fracker also does
        the merging at the end so in that case it is really 'just' there
        to acquire the data'.
        """

        # the fracker required us so we acquire the data and don't do any
        # further processing
        loop = self.system_state['loop']
        scan_parameters = self.system_state['procedure']['parameters']
        network_config = self.system_state['network_config']

        # if we are in the base case (there is only one array in the
        # scan_parameters) and the loop flag has been set, the
        # DataField preforms the measurement
        if loop and len(scan_parameters) == 1:
            # open the socket to the daq coordinator
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(
                f"tcp://{network_config['daq_coordinator']['hostname']}:"
                f"{network_config['daq_coordinator']['port']}")

            # load the configurations
            try:
                calibration = yaml.safe_load(
                        self.input()['full-calibration'].read())
            except KeyError:
                calibration = {}

            # perform the scan
            output_files = self.output()['data']
            output_configs = [os.path.splitext(of.path)[0] + '.yaml'
                              for of in output_files]
            system_state = cfu.unfreeze(self.system_state)
            subtask_states = cfu.generate_subsystem_states(system_state)
            for raw_file, output_config, state in\
                    zip(output_files, output_configs, subtask_states):
                # if the file exists then simply skip it as we are in
                # a rerun as the unpacker/fracker failed
                if Path(raw_file.path).exists():
                    continue

                # generate the complete config and save it as the run config
                complete_config = cfu.generate_run_config(
                        subtask_states, calibration)
                serialized_config = yaml.safe_dump(complete_config)
                with open(output_config, 'w') as run_config:
                    run_config.write(serialized_config)

                # send the measurement command to the backend starting the
                # measurement
                socket.send_string('measure;'+serialized_config)
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
        elif not self.system_state['event_mode']:
            in_files = [data_file.path for data_file in self.input()['data']]
            # run the compiled turbo pump if available
            if shutil.which('turbo-pump') is not None:
                if len(in_files) == 1:
                    shutil.copy(in_files[0], self.output()['data'].path)
                    return
                result = anu.run_turbo_pump(self.output()['data'].path,
                                            in_files)
                if result != 0:
                    raise DAQError("turbo-pump crashed")
            # otherwise run the python version
            else:
                anu.merge_files(in_files, self.output()['data'].path,
                                self.system_state['event_mode'])
            for file in in_files:
                os.remove(file)


class Fracker(luigi.Task):
    """
    convert the format of the raw data into something that can be
    used by the distilleries
    """
    # parameters describing the position of the parameters in the task
    # tree
    id = luigi.IntParameter(significant=True)
    system_state = luigi.DictParameter(significant=True)
    priority = luigi.OptionalParameter(significant=False, default=0)

    def requires(self):
        return DataField(id=self.id,
                         system_state=self.system_state)

    def output(self):
        """
        generate the output filenames for the fracker
        """
        if self.system_state['event_mode']:
            output = {}
            output['full-calibration'] = self.input()['full-calibration']
            output['data'] = []
            for raw_file in self.input()['data']:
                processed_file_path = Path(
                        os.path.splitext(raw_file.path)[0] + '.h5')
                output['data'].append(luigi.LocalTarget(processed_file_path))
            return output
        else:
            out_file = self.system_state['name'] + str(self.id) + '_merged.h5'
            output_path = self.system_state['output_path']
            full_output_path = Path(output_path) / out_file
            return luigi.LocalTarget(full_output_path)

    def run(self):
        subtask_states = cfu.generate_subsystem_states(self.system_state)
        event_mode = self.system_state['event_mode']
        expected_files = list(map(lambda x: x.path, self.output()['data']))
        data_columns = self.system_state['procedure']['data_columns']
        for i, (raw_file, run_state, processed_file) in enumerate(zip(
                    self.input()['data'],
                    subtask_states,
                    self.output()['data'])):
            # compute the paths of the different files produced by the fracker
            data_file_base_name = os.path.splitext(raw_file.path)[0]
            formatted_data_base_name = os.path.splitext(processed_file.path)[0]
            if data_file_base_name == formatted_data_base_name:
                raise DAQConfigError(
                        f'Filenames do not match {data_file_base_name}, '
                        f'{formatted_data_base_name}')
            unpacked_file_path = Path(data_file_base_name + '.root')
            formatted_data_path = processed_file.path
            config_file_path = data_file_base_name + '.yaml'

            # load configuration
            with open(config_file_path, 'r') as config_file:
                complete_config = yaml.safe_load(config_file.read())

            # check if the formatted file allready exists
            if formatted_data_path.exists():
                continue

            # attempt to unpack the files into root files using the unpack
            # command
            result = anu.unpack_raw_data_into_root(
                    raw_file.path,
                    unpacked_file_path,
                    raw_data=event_mode)
            # if the unpaack command failed remove the raw file to
            # trigger the Datafield to rerun the data taking
            if result != 0 and unpacked_file_path.exists():
                os.remove(unpacked_file_path)
                os.remove(raw_file.path)
                continue
            if not unpacked_file_path.exists():
                os.remove(raw_file.path)
                continue

            # if the fracker can be found run it
            if shutil.which('fracker') is not None:
                retval = anu.run_compiled_fracker(
                        str(unpacked_file_path.absolute()),
                        str(formatted_data_path.absolute()),
                        complete_config,
                        event_mode,
                        data_columns)
                if retval != 0:
                    print("The fracker failed!!!")
                    if formatted_data_path.exists():
                        os.remove(formatted_data_path)
            # otherwise fall back to the python code
            else:
                try:
                    anu.reformat_data(unpacked_file_path,
                                      formatted_data_path,
                                      complete_config,
                                      event_mode,
                                      data_columns)
                except KeyInFileError:
                    os.remove(unpacked_file_path)
                    os.remove(raw_file.path)
                    continue
                except FileNotFoundError:
                    continue
            os.remove(unpacked_file_path)

        # check if the unpacker or fracker have failed
        for formatted_file_path in expected_files:
            if not formatted_file_path.exists():
                raise ValueError('An unpacker failed, '
                                 'the datenraffinerie needs to be rerun')

        # run the compiled turbo pump if available
        if not event_mode:
            if shutil.which('turbo-pump') is not None:
                if len(expected_files) == 1:
                    shutil.copy(expected_files[0], self.output()['data'].path)
                    return
                anu.run_turbo_pump(self.output()['data'].path, expected_files)
            # otherwise run the python version
            else:
                anu.merge_files(expected_files, self.output()['data'].path,
                                event_mode)
            # assuming the merge worked, remove the partial files
            for file in expected_files:
                os.remove(file)
