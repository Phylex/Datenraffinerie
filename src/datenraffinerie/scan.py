"""
Module containing the classes that together constitute a measurement
and encapsulate the different steps needed to take a measurement using the
hexaboard
"""
from pathlib import Path
from functools import reduce
from multiprocessing import Process, Queue
import os
from time import sleep
import operator
import shutil
import luigi
import yaml
import zmq
from uproot.exceptions import KeyInFileError
from . import dict_utils as dtu
from . import config_utilities as cfu
from . import analysis_utilities as anu
from .daq_coordination import DAQCoordCommand, DAQCoordResponse
from .config_errors import DAQError
from luigi.parameter import ParameterVisibility
from luigi import Nop


class Well(luigi.Task):
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
    system_state = luigi.DictParameter(significant=True,
                                       visibility=ParameterVisibility.PRIVATE)
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
        from .valve_yard import ValveYard
        if self.system_state['procedure']['calibration'] is not None:
            return ValveYard(system_state=self.system_state,
                             task_name=self.system_state['procedure']['calibration'],
                             priority=self.priority)

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
        name = self.system_state['procedure']['name']
        output_dir = Path(self.system_state['output_path'])
        output = {}
        full_calib_path = output_dir / 'full-calibration.yaml'
        output['full-calibration'] = luigi.LocalTarget(
                full_calib_path.resolve())
        run_ids = reduce(operator.mul,
                         map(lambda x: len(x['values']),
                             self.system_state['procedure']['parameters']))
        output['default'] = luigi.LocalTarget(output_dir /
                                              name + '_full_init.yaml')
        output['data'] = []
        output['raw'] = []
        output['config'] = []
        for i in run_ids:
            output['raw'].append(
                    luigi.LocalTarget(output_dir / name + f'_{i}.raw',
                                      format=Nop))
            output['config'].append(
                    luigi.LocalTarget(output_dir / name + f'_{i}.yaml'))
            if not self.system_state['procedure']['merge']:
                output['data'].append(
                        luigi.LocalTarget(output_dir / name + f'_{i}.h5'))
            else:
                output['data'].append(
                        luigi.LocalTarget(output_dir / name + '_merged.h5'))
        return output

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
        self.system_state = cfu.unfreeze(self.system_state)
        network_config = self.system_state['network_config']

        # open the connection to the daq coordinator
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(
            f"tcp://{network_config['daq_coordinator']['hostname']}:"
            f"{network_config['daq_coordinator']['port']}"
        )
        # load the configurations
        try:
            with self.input()['full-calibration'].open('r') as calibf:
                calibration = yaml.safe_load(calibf.read())
        except KeyError:
            calibration = {}

        # generate the default config
        default_config = cfu.generate_system_default_config(
                self.system_state['procedure'])

        # generate initial config and apply calibration
        initial_config = cfu.generate_init_config(
                self.system_state['procedure'])
        dtu.update_dict(initial_config, calibration, in_place=True)

        # write

        # generate the patches for the daq procedure
        daq_patches = cfu.generate_patches(self.system_state)

        # set up the fracker subprocesses
        fracker_task_queue = Queue()
        fracker_processes = []
        for i in range(self.system_state['workers']):
            p = Process(target=self.frack, args=(fracker_task_queue,
                                                 default_config))
            fracker_processes.append(p)

        # aquire lock from the daq coordinator
        lock_key = None
        retries = 100
        while True:
            command = DAQCoordCommand(command='acquire lock')
            socket.send(command.serialize())
            message = socket.recv()
            response = DAQCoordResponse.parse(message)
            if response['type'] == 'lock':
                if response['content'] is None:
                    sleep(.5)
                    retries -= 1
                    if retries > 0:
                        continue
                    else:
                        socket.close()
                        context.term()
                        raise DAQError(
                            "Failed to aquire Lock in procedure: "
                            f"{self.system_state['procedure']['name']}")
                else:
                    lock_key = response['content']
                    break
            elif response['type'] != 'lock':
                raise DAQError(
                        "Failed to aquire lock, received unexpected response"
                        f"{response}"
                        )

        # ------------------ lock aquired ---------------------------

        # load default config
        command = DAQCoordCommand(
                command='load defaults',
                locking_token=lock_key,
                config=default_config
        )
        socket.send(command.serialize())
        resp = socket.recv()
        resp = DAQCoordResponse.parse(resp)
        if resp['type'] != 'ack':
            raise DAQError(f"received unexpected repsonse: {resp}")

        # compute the filenames for the runs
        output_files = self.output()
        for patch, raw_file, config_file in\
                zip(daq_patches, output_files['raw'], output_files['config']):
            # build run config and write it to disk
            if raw_file.exists():
                continue
            run_config = dtu.update_dict(initial_config, patch)
            serialized_config = yaml.safe_dump(run_config)
            with config_file.open('w') as cf:
                cf.write(serialized_config)

            # send measure command to daq coordinator
            command = DAQCoordCommand(
                    type='measure',
                    config=run_config,
                    locking_token=lock_key
            )
            socket.send(command.serialize())
            message = socket.recv()
            response = DAQCoordResponse.parse(message)
            if response['type'] == 'data':
                with raw_file.open('w') as raw_data_file:
                    raw_data_file.write(response['data'])

            # put the fracking tasks on the queue
            columns = self.system_state['procedure']['data_columns']
            mode = self.system_state['procedure']['mode']
            command = 'format'
            fracker_task_queue.put((command, raw_file.path,
                                    config_file.path,
                                    columns, mode))

        # stop fracking fracker_processes
        for p in fracker_processes:
            fracker_task_queue.put(('stop', '', '', '', ''))
        for p in fracker_processes:
            p.join()

        # release the lock
        command = DAQCoordCommand(type='release lock',
                                  locking_token=lock_key)
        socket.send(command.serialize())
        resp = DAQCoordResponse.parse(socket.recv())
        if resp['type'] != 'ack':
            raise DAQError(f'Error from the daq coordinator: {resp}')

        # ------------------------- lock released -------------------------

        # join all previous tasks
        # merge the files if the procedure is configured to do so
        if self.system_state['merge']:
            raw_files = [r.path for r in self.output()['raw']]
            fracked_file_paths = [
                    Path(os.path.splitext(rf)[0] + '.h5').absolute()
                    for rf in raw_files
            ]
            for p in fracked_file_paths:
                if not Path(p).exists():
                    base_name = os.path.splitext(p.resolve())[0]
                    os.remove(base_name + '.raw')
                    raise DAQError(f'Fracker subtask failed, '
                                   f'{base_name + "h5"} could not be found')

            if len(fracked_file_paths) == 1:
                shutil.copy(fracked_file_paths[0],
                            self.output()['data'].path)
                return
            result = anu.run_turbo_pump(self.output()['data'].path,
                                        fracked_file_paths)
            if result != 0:
                raise DAQError("turbo-pump crashed")

    def frack_data(raw_data_queue, default_config):
        # TODO implement queue logic
        command, raw_file_path, config_file_path, columns, mode =\
                raw_data_queue.get()
        while command != "stop":
            unpacked_file_path = os.path.splitext(raw_file_path)[0] + '.root'
            formatted_data_path = os.path.splitext(raw_file_path)[0] + '.h5'
            result = anu.unpack_raw_data_into_root(
                    raw_file_path,
                    unpacked_file_path,
            )
            # if the unpaack command failed remove the raw file to
            # trigger the Datafield to rerun the data taking
            if result != 0 and unpacked_file_path.exists():
                os.remove(unpacked_file_path)
                os.remove(raw_file_path)
                continue
            if not unpacked_file_path.exists():
                os.remove(raw_file_path)
                continue
            with open(config_file_path, 'r') as rc:
                run_config = yaml.safe_load(rc.read())
            complete_config = dtu.update_dict(default_config, run_config),
            # if the fracker can be found run it
            if shutil.which('fracker') is not None:
                retval = anu.run_compiled_fracker(
                        str(unpacked_file_path.absolute()),
                        str(formatted_data_path.absolute()),
                        complete_config,
                        mode,
                        columns)
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
                                      mode,
                                      columns)
                except KeyInFileError:
                    os.remove(unpacked_file_path)
                    os.remove(raw_file_path)
                    continue
                except FileNotFoundError:
                    continue
            os.remove(unpacked_file_path)
            command, raw_file_path, config_file_path, columns, mode =\
                raw_data_queue.get()
