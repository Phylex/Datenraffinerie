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
import os
import logging
import shutil
from pathlib import Path
import uuid
import zmq
import yaml
from dict_utils import diff_dict, update_dict

module_logger = logging.getLogger(__name__)


def _filter_out_network_config(config):
    """
    As there is minimal network configuration inside the daq system config
    we need to filter this out to be able to pass along the parameters that
    are intended for the actual server and client

    Also has to handle data weirdly because of technical debt in the daq c++
    software
    """
    # this weird contraption needs to be build because the current zmq server
    # and client expect the ENTIRE configuration (including hexaboard and every
    # other component to be sent to them
    out_config = {}
    hostname = None
    port = None
    for key, value in config.items():
        if 'hostname' == key:
            hostname = value
        elif 'port' == key:
            port = value
        else:
            out_config[key] = value
    return out_config, hostname, port


class DAQAdapter():
    """
    A representation of the DAQ side of the system. It encapsulates the
    zmq-server and zmq-client
    """
    variant_key_map = {'server': 'daq', 'client': 'global'}

    def __init__(self, variant: str, hostname: str,
                 port: int):
        # set up the logger for this object
        self.logger = logging.getLogger(
                __name__+'.TargetAdapter')

        # initialize the connection to the target server
        self.hostname = hostname
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
        self.variant = variant
        self.running = False

        # initialize the configuration properly
        self.configuration = {self.variant_key_map[self.variant]: {}}

    def _clean_configuration(self, config):
        config, _, _ = \
                _filter_out_network_config(config)
        try:
            config = config[self.variant_key_map[self.variant]]
        except KeyError:
            try:
                config = config[self.variant]
            except KeyError:
                config = {}
        config = {self.variant_key_map[self.variant]: config}
        return config

    def update_config(self, config):
        update_dict(self.configuration,
                    self._clean_configuration(config),
                    in_place=True)

    def initialize(self, initial_config: dict):
        initial_config, _, _ = _filter_out_network_config(initial_config)
        self.logger.debug("initializing")
        self.configuration = initial_config
        self.socket.send_string("initalize", zmq.SNDMORE)
        config_string = yaml.dump(self.configuration)
        self.logger.debug("sending config:\n" + config_string)
        self.socket.send_string(config_string)
        rep = self.socket.recv_string()
        if rep != "initialized":
            raise ValueError("Server not successfully initialized")
            self.logger.critical(
                    "Server not successfully initialized."
                    f" Received {rep}")
        else:
            self.logger.debug(f"Received reply: {rep}")

    def configure(self, config: dict = {}, use_cache_output=False):
        self.logger.info('Configuring')
        config = self._clean_configuration(config)
        if use_cache_output:
            current_config = self.configuration
            config = update_dict(self.configuration, config)
            write_config = diff_dict(current_config, config)
            self.configuration = config
        else:
            update_dict(self.configuration, config, in_place=True)
            write_config = config

        # if the config is empty we don't have to write anything
        if write_config == {}:
            self.logger.debug("No new configuration to transmit")
            return
        config_string = yaml.dump(write_config)
        self.logger.debug(f"Sending config:\n{config_string}")
        self.socket.send_string('configure', zmq.SNDMORE)
        self.socket.send_string(config_string)
        reply = self.socket.recv_string()
        if "configured" != reply:
            raise ValueError(
                    "The configuration cannot be "
                    f" written to {self.hostname}. The daq component"
                    f"responded with {reply}")
        self.logger.info("Configuration successful")

    def reset(self):
        self.logger.debug("resetting roc by closing and reopening "
                          "the connection")
        self.socket.close()
        self.context.destroy()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://"+str(self.ip)+":"+str(self.port))
        self.configuration = {}

    def start(self):
        """
        Start the aquisition of the data on the server and client
        """
        self.logger.info("Starting data-taking")
        status = "none"
        self.socket.send_string("status")
        status = self.socket.recv_string()
        if status == "configured":
            self.socket.send_string("start")
        else:
            raise ValueError("Server not ready to start data taking")
        status = self.socket.recv_string()
        self.logger.debug(f"Status received from Server: {status}")
        if status != "running":
            raise ValueError(f"Server not running, status: {status}")
        self.info("Data is being aquired")
        return

    def stop(self):
        self.logger.info("Stopping data-taking")
        self.socket.send_string("stop")
        rep = self.socket.recv_string()
        self.logger.debug(f"Status received from Server: {rep}")
        if rep != "configured":
            raise ValueError("Server did not stop correctly")
        return

    def take_data(self):
        """
        check if the current aquisition is ongoing or not
        """
        self.logger.info('Starting data taking run')
        self.start()
        self.socket.send_string("status")
        status = self.socket.recv_string()
        self.logger.debug(f"Checking if run is done, received: {status}")
        while status == "running":
            self.socket.send_string("status")
            status = self.socket.recv_string()
        if status == "configured":
            return
        else:
            raise ValueError('Invalid status from the DAQ server: {status}')


class DAQSystem:
    """
    A class that encapsulates the interactions
    with the DAQ-system (the zmq-[server|client])

    The class implements a small two-state state machine that only allows
    data-taking via the 'take_data' function after the 'start_run' function
    has been called. The data taking is stopped via the 'stop_run'
    function that
    """

    def __init__(self, server_hostname: str, server_port: int,
                 client_hostname: str, client_port: int):
        """
        initialise the daq system by initializing it's components (the client
        and server)
        """
        # set up the server part of the daq system (zmq-server)
        self.logger = logging.getLogger(__name__+'.DAQSystem')
        self.server = DAQAdapter('server', server_hostname, server_port)
        # set up the client part of the daq system (zmq-client)
        # the wrapping with the global needs to be done so that the client
        # accepts the configuration
        self.client = DAQAdapter('client', client_hostname, client_port)

    def __del__(self):
        self.tear_down_data_taking_context()

    def initalize(self, initial_config: dict):
        self.server.initialize(initial_config)
        self.client.initialize(initial_config)

    def configure(self, daq_config: dict = None):
        """
        configure the daq system before starting a data-taking run.
        """
        self.client.configure(daq_config, use_cache_output=True)
        self.server.configure(daq_config, use_cache_output=True)

    def setup_data_taking_context(self):
        """
        setup the folders and the zmq-client configuration

        Function is called at initialisation and should not be called
        by user code

        Prepare a folder to save the raw data in and set up the client
        configuration so that the zmq-client writes into that folder
        It is expected that the folder is empty before every measurement
        as the filename of the zmq-client is not easily predictable
        """
        # get the location for the placement of the files by the
        # zmq-client, if one is already configured then use it
        # otherwise generate a new one
        client_config = {}
        self.procedure_uuid = uuid.uuid1().hex
        self.daq_data_folder = Path('/tmp') / self.procedure_uuid
        client_config['outputDirectory'] = str(self.daq_data_folder)
        client_config['run_type'] = "Datenraffinerie"
        self.client.update_config({"global": client_config})
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
        self.client.start()
        self.server.take_data()
        data_files = os.listdir(self.daq_data_folder)
        if len(data_files) > 1:
            raise ValueError(
                    "More than one file was found in the"
                    f" {self.daq_data_folder.resolve()} folder")
        data_file = data_files[0]
        shutil.move(self.daq_data_folder / data_file, output_data_path)
        self.server.stop()
        self.client.stop()

    def tear_down_data_taking_context(self):
        """
        The complement to the 'start_run' function stops the run and cleans up
        after the run has completed
        """
        try:
            if os.path.exists(self.daq_data_folder):
                for file in self.daq_data_folder.iterdir():
                    os.remove(file)
                os.rmdir(self.daq_data_folder)
        except AttributeError:
            return
