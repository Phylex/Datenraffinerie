"""
Module containing the adapters to the daq system consisting of the
zmq-server, zmq-client and the zmq_i2c-server. This module is and
should be the only point of interaction between the Datenraffinerie
and the daq services provided by the above mentioned programs, as
such it encapsulates the peculiarities of the underlying DAQ system
and provides a uniform API for the Datenraffinerie to use.

This file needs to be adapted if the underlying DAQ programs change
their behaviour
"""
from time import sleep
import os
from pathlib import Path
import uuid
import zmq
import yaml
import pid
from config_utilities import diff_dict, update_dict


class DAQError(Exception):
    def __init__(self, message):
        self.message = message
class ControlAdapter:
    """
    Class that encapsulates the configuration and communication to either
    the client or the server of the daq-system
    """

    def __init__(self, config):
        """
        Initialize the data structure on the control computer (the one
        coordinating everything) and connect to the system component.
        Do not load any configuraion yet
        """
        self.hostname = config['hostname']
        self.port = config['port']
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
        self.configuration = config

    def reset(self):
        """
        reset the connection with the system component, may not reset the
        state of the component
        """
        self.socket.close()
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")

    def configure(self, config=None):
        """
        send the configuration to the corresponding system component and wait
        for the configuration to be completed
        """
        config = self._filter_out_network_config(config)

        if config is not None:
            write_config = diff_dict(self.configuration, config)
        else:
            write_config = self.configuration
        # if there is no difference between the configs simply return
        if len(write_config.items()) == 0:
            return
        self.socket.send_string("configure")
        rep = self.socket.recv_string()
        if "ready" not in rep.lower():
            raise ValueError(
                "The configuration cannot be "
                f" written to {self.hostname}. The target"
                f"responded with {rep}")
        self.socket.send_string(yaml.dump(write_config))
        rep = self.socket.recv_string()
        self.configuration = update_dict(self.configuration, write_config)
        return

    @staticmethod
    def _filter_out_network_config(config):
        """
        As there is minimal network configuration inside the daq system config
        we need to filter this out to be able to pass along the parameters that
        are intended for the actual server and client
        """
        out_config = {}
        for key, value in config.items():
            if ('hostname' not in key) and ('port' not in key):
                out_config[key] = value
        return out_config


class TargetAdapter(ControlAdapter):
    """
    The adapter that is used to control the Targets (so ROCs and
    Hexboards) currrently uses the zmq_i2c server
    """

    def read_config(self, parameter: dict):
        """
        Read the values set on the ROC directly from it

        Arguments:
            paramter, dict: The parameter that should be read from the ROC

        Returns:
            the dict containing the requested parameter(s) passed in the
            parameter argument set to the value read from the ROC,
            if no parameter is passed the target configuration server will
            check which values of the configuration are cached and read
            those values from the ROC update it's cache and return the new
            values to this function which will in turn return these values
            to the caller
        """
        self.socket.send_string("read")
        _ = self.socket.recv_string()
        if parameter:
            self.socket.send_string(yaml.dump(parameter))
        else:
            # this reads all the values in the cache of the zmq server
            # from the roc and then returns what is in the cache
            self.socket.send_string("")
        return yaml.safe_load(self.socket.recv_string())

    def read_pwr(self):
        # only valid for hexaboard/trophy systems
        self.socket.send_string("read_pwr")
        rep = self.socket.recv_string()
        pwr = yaml.safe_load(rep)
        return(pwr)

    def resettdc(self):
        self.socket.send_string("resettdc")
        rep = self.socket.recv_string()
        return(yaml.safe_load(rep))

    def measadc(self, yamlNode):
        # only valid for hexaboard/trophy systems
        self.socket.send_string("measadc")
        rep = self.socket.recv_string()
        if rep.lower().find("ready") < 0:
            print(rep)
            return
        if yamlNode:
            config = yamlNode
        else:
            config = self.yamlConfig
        self.socket.send_string(yaml.dump(config))
        rep = self.socket.recv_string()
        adc = yaml.safe_load(rep)
        return(adc)


class DAQAdapter(ControlAdapter):
    """
    Encapsulate the Access to the daq-client and server of the daq system.
    """

    def start(self):
        """
        Start the aquisition of the data on the server and client
        """
        rep = ""
        while "running" not in rep.lower():
            self.socket.send_string("start")
            rep = self.socket.recv_string()
            print(rep)

    def is_done(self):
        """
        check if the current aquisition is ongoing or not
        """
        self.socket.send_string("run_done")
        rep = self.socket.recv_string()
        if "notdone" in rep:
            return False
        return True

    def stop(self):
        """
        stop the currently running measurement
        """
        self.socket.send_string("stop")
        rep = self.socket.recv_string()
        print(rep)

    def delay_scan(self):
        """
        perform a delay scan that tries to asses the timing conditions
        for the link between the roc and the hexacontroller
        """
        # only for daq server to run a delay scan
        rep = ""
        while "delay_scan_done" not in rep:
            self.socket.send_string("delayscan")
            rep = self.socket.recv_string()
            print(rep)

    def configure(self, config):
        if not self.is_done():
            raise DAQError("DAQ system is running, it should not be")
        self.stop()
        super().configure(config)

class DAQSystem:
    """
    A class that abstracts encapsulates the interactions
    with the DAQ-system (the hexacontroller, hexaboard and zmq-[server|client])

    The class implements a small two-state state machine that only allows data-taking
    via the 'take_data' function after the 'start_run' function has been called.
    The data taking is stopped via the 'stop_run' function that 
    """

    def __init__(self, daq_config):
        """ initialise the daq system by initializing it's components (the client and
        server) during this step the actual system components are not loaded with
        the configuration, as it is expected that 
        """
        # set up the server part of the daq system (zmq-server)
        self.server_config = daq_config['server']
        self.client_config = daq_config['client']
        self.run_in_progress = False
        self.daq_data_base_path = None
        self.daq_data_folder = None
        self.server = DAQAdapter(self.server_config)
        # set up the client part of the daq system (zmq-client)
        self.client = DAQAdapter(self.client_config)

    def __del__(self):
        self.stop_run()

    def _update_internal_configuration(self, daq_config: dict):
        if 'server' in daq_config.keys():
            self.server_config = update_dict(self.server_config,
                                             daq_config['server'])
        if 'client' in daq_config['client']:
            self.client_config = update_dict(self.client_config,
                                             daq_config['client'])

    def configure(self, daq_config: dict = None):
        """
        configure the daq system before starting a data-taking run.

        This function should not be run by user code. The user should
        call 'start_run' to start a run, which configures the daq_system
        appropriately and performs all other necessary steps.
        """
        if daq_config is not None:
            self._update_internal_configuration(daq_config)
        self.client.configure(self.client_config)
        self.server.configure(self.server_config)

    def setup_data_taking_context(self):
        """
        Prepare a folder to save the raw data in and set up the client
        configuration so that the zmq-client writes into that folder
        It is expected that the folder is empty before every measurement
        as the filename of the zmq-client is not easily predictable
        """
        if self.run_in_progress:
            raise DAQError("A run has already been started")
        # get the location for the placement of the files by the
        # zmq-client, if one is already configured then use it
        # otherwise generate a new one
        if 'outputDirectory' in self.client_config.keys():
            self.daq_data_base_path = Path(
                    self.client_config['outputDirectory'])
        else:
            self.daq_data_base_path = Path('/tmp')
            self.client_config['outputDirectory'] = \
                str(self.daq_data_base_path)
        if 'run_type' in self.client_config.keys():
            self.run_uuid = self.client_config['run_type']
            self.daq_data_folder = self.daq_data_base_path /\
                self.run_uuid
        else:
            self.run_uuid = uuid.uuid1().hex
            self.daq_data_folder = self.daq_data_base_path /\
                self.run_uuid
        if not os.path.isdir(self.daq_data_folder):
            os.mkdir(self.daq_data_folder)

    def take_data(self, output_data_path):
        """
        function that encapsulates the data taking currently done via the
        zmq-client program. The zmq-client currently has a particular way of
        naming the files it creates that is incompatible with the way luigi
        expects the files to be named to be able to evaluate if a task has
        completed or not.

        The strategy here is to configure the zmq-client to put it's output
        into the /tmp folder of the machine running the client and the Daten-
        raffinerie and then to copy that file from the location in tmp to
        the location given by the 'output_data_path' argument of the function
        after the daq for the run has concluded
        """
        if not self.run_in_progress:
            raise DAQError("A DAQ run has to be started via the 'start_run'"
                           " function before data can be taken")
        if not self.server.is_done():
            raise DAQError("The server should not be running an acquisition")
        self.client.start()
        self.server.start()
        while not self.server.is_done():
            sleep(0.01)
        files = list(self.daq_data_folder.glob('*.raw'))
        if len(files) > 1:
            raise DAQError("More than one file was found in the"
                           f" {self.daq_data_folder.resolve()} folder")
        os.rename(files[0], output_data_path)
        self.server.stop()
        self.client.stop()

    def tear_down_datat_taking_context(self):
        """
        The complement to the 'start_run' function stops the run and cleans up
        after the run has completed
        """
        if os.path.exists(self.daq_data_folder):
            for file in self.daq_data_folder.iterdir():
                os.remove(file)
            os.rmdir(self.daq_data_folder)
