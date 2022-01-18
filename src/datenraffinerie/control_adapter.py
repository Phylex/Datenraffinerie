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
import logging
import shutil
from pathlib import Path
import uuid
import zmq
import yaml
from .config_utilities import diff_dict, update_dict

module_logger = logging.getLogger('hexactrl_shostnameipt.control_adapter')

class DAQError(Exception):
    def __init__(self, message):
        self.message = message


class DAQConfigError(Exception):
    def __init__(self, message):
        self.message = message


class ControlAdapter:
    """
    Class that encapsulates the configuration and communication to either
    the client and server of the daq-system or target.
    """

    def __init__(self, default_config: dict, hostname: str = None, port: str = None):
        """
        Initialize the data structure on the control computer (the one
        coordinating everything) and connect to the system component.
        Do not load any configuraion yet this is done to be able to
        load the reset / power on configuration. any change of the
        configuration after the initialisation will be written to the
        target program
        """
        self.logger = logging.getLogger(
                'hexactrl_script.contol_adapter.ControlAdapter')
        config, config_hostname, config_port = self._filter_out_network_config(
                default_config)
        if hostname is None:
            if config_hostname is None:
                raise DAQConfigError('No hostname given')
            hostname = config_hostname
        if port is None:
            if config_port is None:
                raise DAQConfigError('No port given')
            port = config_port
        self.hostname = hostname
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
        self.configuration = config
        self.default_config = config
        # this is used to determin if to send the full config
        #-to the target if 'configure' is called without an argument
        self.config_written = False

    def reset(self):
        """
        reset the connection with the system component, may not reset the
        state of the component
        """
        self.socket.close()
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")

    def configure(self, config=None, force=False, default_overlay=True):
        """
        send the configuration to the corresponding system component and wait
        for the configuration to be completed

        This function has to pick the right configuration to send depending on
        the force and diff flags

        Arguments:
            default_overlay: Specifies that the config received is an overlay
            of the default_configuration. Using that information an appropriate
            diff is calculated and sent to the backend system

            force: if this flag is set the cache is ignored. In this case
            the cache is updated with the new values from the config passed
            in (if there is any) and then the new configuration is sent to
            the backend.
            if this flag is false/unset then the diff between the config
            passed in and the cache is sent. If no config is passed, then
            the function checks if the values of the cache have been sent
            to the endpoint yet. If the 'config_written' flag is set it exits
            otherwise it configures the endpoint with the current content
            of the cache
        """
        if config is not None:
            config, _, _ = self._filter_out_network_config(config)
            if default_overlay is True:
                config = update_dict(self.default_config, config)
                write_config = diff_dict(self.configuration, config)
            else:
                write_config = diff_dict(self.configuration, config)
                if force is True:
                    write_config = self.configuration
        else:
            if force is True:
                write_config = self.configuration
            elif self.config_written is False:
                write_config = diff_dict(self.default_config,
                                         self.configuration)
            else:
                write_config = None
        # if there is no difference between the configs simply return
        if write_config is None:
            return

        rep = self._send_and_log('configure')
        if "ready" not in rep.lower():
            raise ValueError(
                    "The configuration cannot be "
                    f" written to {self.hostname}. The target"
                    f"responded with {rep}")
        serialized_config = yaml.dump(write_config)
        self.logger.debug(f"Sending configuration:\n {serialized_config}"
                f" to {self.hostname}:{self.port}")
        self.socket.send_string(serialized_config)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
        if not rep == 'Configured' and not rep == 'ROC(s) CONFIGURED\n...\n':
            raise DAQError("The configuration endpoint did not indicate "
                           " a successful configuration")
        self.configuration = update_dict(self.configuration,
                                         write_config,
                                         in_place=True)
        self.config_written = True

    def _send_and_log(self, msg: str):
        self.logger.debug(f"Sending string '{msg}' to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
        return rep

    @staticmethod
    def _filter_out_network_config(config):
        """
        As there is minimal network configuration inside the daq system config
        we need to filter this out to be able to pass along the parameters that
        are intended for the actual server and client

        Also has to handle data weirdly because of technical debt in the daq c++
        software
        """
        if config is None:
            return None
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

    def read(self):
        """read the current config from the target
        :returns: Dictionary with the current config
            of the target
        """
        return self._send_and_log('read')


class TargetAdapter(ControlAdapter):
    """
    The adapter that is used to control the Targets (so ROCs and
    Hexboards) currrently uses the zmq_i2c server
    """

    def __init__(self, initial_config: dict):
        """
        Initializes the target Board and loads an initial config onto it

        Arguments:
            initial_config: This config is assumed to be the goal state
            of the system, if it is passed during initialisation it is
            written to the target system
        """
        try:
            hostname = initial_config['hostname']
            port = initial_config['port']
        except KeyError as err:
            raise DAQConfigError('A hostname and port are not '
                                 ' present in any configuration'
                                 ' received') from err
        super().__init__(initial_config, hostname=hostname, port=port)
        self.logger = logging.getLogger(
                'hexactrl_script.contol_adapter.TargetAdapter')
        self.configure()

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
        _ = self._send_and_log('read')
        if parameter:
            read_params = yaml.dump(parameter)
            self.logger.debug(f"Sending parameters to read:\n {read_params}"
                    f" to {self.hostname}:{self.port}")
            self.socket.send_string(read_params)
        else:
            # this reads all the values in the cache of the zmq server
            # from the roc and then returns what is in the cache
            self.logger.debug(f"Sending parameters to read:\n ''"
                    f" to {self.hostname}:{self.port}")
            self.socket.send_string("")
            read_values = self.socket.recv_string()
        self.logger.debug("Received params read from target on "
                f"{self.hostname}:{self.port}:\n"
                f"{read_values}")
        return yaml.safe_load(read_values)

    def read_pwr(self):
        # only valid for hexaboard/trophy systems
        rep = self._send_and_log('read_pwr')
        pwr = yaml.safe_load(rep)
        return pwr

    def resettdc(self):
        rep = self._send_and_log('resettdc')
        return yaml.safe_load(rep)

    def measadc(self, yamlNode: dict = None) -> dict:
        # only valid for hexaboard/trophy systems
        self.socket.send_string("measadc")
        rep = self.socket.recv_string()
        if rep.lower().find("ready") < 0:
            return
        if yamlNode is not None:
            config = yamlNode
        else:
            config = self.configuration
        self.socket.send_string(yaml.dump(config))
        rep = self.socket.recv_string()
        adc = yaml.safe_load(rep)
        return adc


class DAQAdapter(ControlAdapter):
    """
    A representation of the DAQ side of the system. It encapsulates the
    zmq-server and zmq-client
    """
    variant_key_map = {'server': 'daq', 'client': 'global'}

    def __init__(self, config: dict, variant: str):
        """
        The DAQ adapter needs to modify the configuration format of the
        Datenraffinerie to make it compatible with the current zmq-server
        and client

        Arguments:
            config, dict: The configuration of the DAQ endpoint
            variant, str: either 'server' or 'client'. lets the DAQ adapter
                make the neccesary changes to the config
        """
        self.variant = variant
        super().__init__(config)
        self.logger = logging.getLogger(
                f'hexactrl_script.contol_adapter.DAQAdapter.{self.variant}')
        self.configuration = {self.variant_key_map[self.variant]:
                              self.configuration}
        self.configure()

    def configure(self, config: dict = None):
        """
        workaround for the way the zmq-client/zmq-server handles the
        configuration together with necessary checks for the
        """
        if config is not None:
            config, _, _ = self._filter_out_network_config(config)
            super().configure({self.variant_key_map[self.variant]: config},
                              force=True)
        else:
            super().configure(force=True)

    def get_config(self):
        return self.configuration[self.variant_key_map[self.variant]]

    def start(self):
        """
        Start the aquisition of the data on the server and client
        """
        rep = ""
        while "running" not in rep.lower():
            rep = self._send_and_log('start')

    def is_done(self):
        """
        check if the current aquisition is ongoing or not
        """
        rep = self._send_and_log('run_done')
        if "notdone" in rep:
            return False
        return True

    def stop(self):
        """
        stop the currently running measurement
        """
        rep = self._send_and_log('stop')
        if not rep == 'Data puller stopped' and\
                not rep == 'Stopped':
            raise DAQError('Response of the zmq-client to'
                           " the 'stop' command invalid")

    def delay_scan(self):
        """
        perform a delay scan that tries to asses the timing conditions
        for the link between the roc and the hexacontroller
        """
        # only for daq server to run a delay scan
        rep = ""
        while "delay_scan_done" not in rep:
            rep = self._send_and_log('delayscan')


class DAQSystem:
    """
    A class that abstracts encapsulates the interactions
    with the DAQ-system (the hexacontroller, hexaboard and zmq-[server|client])

    The class implements a small two-state state machine that only allows data-taking
    via the 'take_data' function after the 'start_run' function has been called.
    The data taking is stopped via the 'stop_run' function that 
    """

    def __init__(self, daq_config):
        """
        initialise the daq system by initializing it's components (the client and
        server)
        """
        # set up the server part of the daq system (zmq-server)
        self.daq_data_base_path = None
        self.daq_data_folder = None
        if 'server' not in daq_config.keys():
            raise DAQError("There mus be a 'server' key in the initial"
                           " configuration")
        if 'client' not in daq_config.keys():
            raise DAQError("There mus be a 'client' key in the initial"
                           " configuration")
        server_config, client_config = self.split_config_into_client_and_server(
                daq_config)
        self.server = DAQAdapter(server_config, 'server')
        # set up the client part of the daq system (zmq-client)
        # the wrapping with the global needs to be done so that the client
        # accepts the configuration
        self.client = DAQAdapter(client_config, 'client')
        self._setup_data_taking_context()
        self.client.configure()

    def __del__(self):
        self.tear_down_data_taking_context()

    @staticmethod
    def split_config_into_client_and_server(daq_config: dict):
        """
        convenience function to split the configuration passed to
        the configure method into the client and server part.

        It also compensates for all the config peculiarities of
        the daq programs in their current state.

        Should not be called by the user code!
        """
        server_config = None
        client_config = None
        if 'server' in daq_config.keys():
            server_config = daq_config['server']
        if 'client' in daq_config.keys():
            client_config = daq_config['client']
        return server_config, client_config

    def configure(self, daq_config: dict = None):
        """
        configure the daq system before starting a data-taking run.

        """
        server_config = None
        client_config = None
        if daq_config is not None:
            server_config, client_config = self.split_config_into_client_and_server(
                    daq_config)
        self.client.configure(client_config)
        self.server.configure(server_config)

    def _setup_data_taking_context(self):
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
        client_config = self.client.get_config()
        self.run_uuid = uuid.uuid1().hex
        self.daq_data_folder = Path('/tmp') / self.run_uuid
        client_config['outputDirectory'] = str(self.daq_data_folder)
        client_config['run_type'] = self.run_uuid
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
        self.client.configure()
        self.client.start()
        self.server.start()
        while not self.server.is_done() or\
                len(os.listdir(self.daq_data_folder)) == 0:
            sleep(0.01)
        data_files = os.listdir(self.daq_data_folder)
        if len(data_files) > 1:
            raise DAQError("More than one file was found in the"
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
        if os.path.exists(self.daq_data_folder):
            for file in self.daq_data_folder.iterdir():
                os.remove(file)
            os.rmdir(self.daq_data_folder)
