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
from time import sleep
from .dict_utils import diff_dict, update_dict

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
    variant_key_map = {'server': 'daq', 'client': 'client'}

    def __init__(self, variant: str, hostname: str,
                 port: int, data_port: int):
        # set up the logger for this object
        self.logger = logging.getLogger(
                __name__+f'.{variant}')

        # initialize the connection to the target server
        self.hostname = hostname
        self.ctrl_port = port
        self.data_port = data_port
        self.context = zmq.Context()
        self.logger.info(f'Initializing connection to {variant}')
        self.socket = self.context.socket(zmq.REQ)
        socket_url = f'tcp://{self.hostname}:{self.ctrl_port}'
        self.logger.debug(f'connecting to {socket_url}')
        self.socket.connect(socket_url)
        self.variant = variant
        self.running = False

        # initialize the configuration properly
        self.configuration = {self.variant_key_map[self.variant]: {}}

    def __del__(self):
        self.socket.close()
        self.context.destroy()

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
        self.logger.debug("initializing")
        self.configuration = self._clean_configuration(initial_config)
        # include the data port in the configuration
        self.configuration[self.variant_key_map[self.variant]]['zmqPushPull_port'] \
            = self.data_port
        self.socket.send_string("initialize", zmq.SNDMORE)
        config_string = yaml.dump(self.configuration)
        self.logger.debug("sending config:\n" + config_string)
        self.socket.send_string(config_string)
        rep = self.socket.recv()
        rep = rep.decode('utf-8')
        if rep != "initialized":
            self.logger.critical(
                    "Server not successfully initialized."
                    f" Received: {rep}")
            raise ValueError("Server not successfully initialized")
        else:
            self.logger.debug(f"Received reply: {rep}")

    def configure(self, config: dict = {}, cache=False):
        self.logger.info('Configuring')
        config = self._clean_configuration(config)
        self.logger.debug(f'Updating config with:\n{config}')
        if self.variant == 'client':
            write_config = config
        else:
            # constrain the configuration that should be updated
            # to the configuration in the active menu
            try:
                active_menu = config['daq']['active_menu']
            except KeyError:
                try:
                    active_menu = self.configuration['daq']['active_menu']
                except KeyError:
                    raise ValueError('No Active menu found')
            try:
                current_config = {
                    'daq':
                    {'active_menu': active_menu,
                     'menus': {
                        active_menu:
                        self.configuration['daq']['menus'][active_menu]}
                     }
                    }
            except KeyError:
                current_config = \
                    {'daq':
                     {'active_menu': active_menu,
                      'menus': {active_menu: {}}
                      }
                     }
            config = update_dict(current_config, config)
            # check that we are only configuring the stuff in the active_menu
            if any(map(lambda x: active_menu != x,
                       config['daq']['menus'].keys())):
                raise RuntimeWarning(
                    'Configuring menus that are not the'
                    'active menu, these parameters are going to be'
                    'ignored.')
            self.configuration = update_dict(self.configuration, config)
            if cache:
                write_config = config \
                    if diff_dict(current_config, config) is not None else \
                    {self.variant_key_map[self.variant]: {}}
            else:
                write_config = config

        # if the config is empty we don't have to write anything
        if write_config[self.variant_key_map[self.variant]] == {}:
            self.logger.debug("Configuration did not change, "
                              "skipping configuration of the backend")
            return
        self.logger.debug(f'Writing config:\n{config}')
        config_string = yaml.dump(write_config)
        self.logger.debug(f"Sending config:\n{config_string}")
        self.socket.send_string('configure', zmq.SNDMORE)
        self.socket.send_string(config_string)
        reply = self.socket.recv_string()
        if "configured" != reply:
            self.logger.error(
                    "The configuration cannot be "
                    f" written to {self.hostname}. The daq component"
                    f"responded with {reply}")
            raise ValueError(
                    "The configuration cannot be "
                    f" written to {self.hostname}. The daq component"
                    f"responded with {reply}")
        self.logger.info("Configuration successful")
        self.configuration = update_dict(self.configuration, write_config)

    def reset(self):
        self.logger.debug("resetting daq-server by closing and reopening "
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
        self.logger.debug(f'Checking status of {self.variant}')
        self.socket.send_string("status")
        status = self.socket.recv_string()
        self.logger.debug(f'Current state: {status}')
        if status != "configured":
            raise ValueError("Server not ready to start data taking")
        retries = 50
        post_link_alignment_state = 'configured'
        while retries > 0:
            self.logger.debug(
                    f'Attempting to start backend, {retries} trys remaining')
            self.socket.send_string("start")
            status = self.socket.recv_string()
            if status == 'running':
                post_link_alignment_state = status
                break
            retries -= 1
        # if there where no trys left
        if post_link_alignment_state != 'running':
            self.logger.critical(
                    'Unable to start server, probably bad link alignment')
            raise ValueError(
                    'Unable to Start server, probably bad link alignment')
        self.logger.info(
            f"successfully started backend, current state: {status}")
        return status

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
        # attempt to start server. Server only switches into the
        # running state if the links are aligned.
        # so we query until we run out of tries or the server switches to
        # running
        self.logger.info('links aligned, taking data')
        status = self.start()
        self.logger.info('waiting for run to finish')
        while status == "running":
            self.socket.send_string("status")
            status = self.socket.recv_string()
        if status == "configured":
            self.logger.info('Data taking run completed')
            return
        else:
            self.logger.critical(
                'Invalid status from the DAQ server: {status}')
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

    def __init__(self, server_hostname: str, server_port: int, data_port: int,
                 client_hostname: str, client_port: int):
        """
        initialise the daq system by initializing it's static components
        (and server)
        """
        # set up the server part of the daq system (zmq-server)
        self.logger = logging.getLogger(__name__+'.DAQSystem')
        self.client_started = False
        self.data_port = data_port
        self.server = DAQAdapter('server', server_hostname,
                                 server_port, data_port)
        self.client = DAQAdapter('client', client_hostname, client_port,
                                 self.data_port)
        # set up the client part of the daq system (zmq-client)
        # the wrapping with the global needs to be done so that the client
        # accepts the configuration

    def __del__(self):
        self.tear_down_data_taking_context()

    def initialize(self, initial_config: dict):
        initial_config['client']['serverIP'] = self.server.hostname
        self.client.initialize(initial_config)
        self.server.initialize(initial_config)

    def configure(self, daq_config: dict = None):
        """
        configure the daq system before starting a data-taking run.
        """
        self.client.configure(daq_config, cache=True)
        self.server.configure(daq_config, cache=True)

    def setup_data_taking_context(self):
        client_config = {}
        self.logger.debug('Setting up data taking context')
        self.procedure_uuid = uuid.uuid1().hex
        self.daq_data_folder = Path('/tmp') / self.procedure_uuid
        client_config['outputDirectory'] = str(self.daq_data_folder)
        client_config['run_type'] = "Datenraffinerie"
        if not os.path.isdir(self.daq_data_folder):
            os.mkdir(self.daq_data_folder)
        self.client.configure(
                {self.client.variant_key_map[self.client.variant]:
                 client_config})
        self.logger.debug('Updated client configuration to\n' +
                          yaml.safe_dump(self.client.configuration))
        active_menu = self.server.configuration['daq']['active_menu']
        config_transition_server_config = {}
        config_transition_server_config['daq'] = {}
        config_transition_server_config['daq']['active_menu'] = active_menu
        config_transition_server_config['daq']['menus'] = {}
        config_transition_server_config['daq']['menus'][active_menu] = \
            self.server.configuration['daq']['menus'][active_menu]
        self.server.configure(config_transition_server_config)

    def take_data(self, output_data_path):
        if not self.client_started:
            self.client.start()
            self.client_started = True
        try:
            self.server.take_data()
        except ValueError as err:
            self.client.stop()
            raise ValueError('Data taking failed') from err
        wait_cycles = 20
        data_files = os.listdir(self.daq_data_folder)
        while wait_cycles > 0 and len(data_files) == 0:
            data_files = os.listdir(self.daq_data_folder)
            sleep(.1)
            wait_cycles -= 1
        if len(data_files) != 1:
            raise ValueError(
                    "More than one file was found in the"
                    f" {self.daq_data_folder.resolve()} folder")
        data_file = data_files[0]
        shutil.move(self.daq_data_folder / data_file, output_data_path)

    def tear_down_data_taking_context(self):
        if self.client_started:
            self.client.stop()
            self.client_started = False
        try:
            if os.path.exists(self.daq_data_folder):
                for file in self.daq_data_folder.iterdir():
                    os.remove(file)
                os.rmdir(self.daq_data_folder)
        except AttributeError:
            return
