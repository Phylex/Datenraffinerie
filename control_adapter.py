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
from config_utilities import diff_dict, update_dict

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
    the client or the server of the daq-system
    """

    def __init__(self, config: dict, hostname: str = None, port: str = None):
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
                config)
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

    def configure(self, config=None):
        """
        send the configuration to the corresponding system component and wait
        for the configuration to be completed
        """
        if config is not None:
            config, _, _= self._filter_out_network_config(config)
            write_config = diff_dict(self.configuration, config)

            # This case appears during the use of the zmq i2c server
            # as there the first write access should not write the entire
            # config as we expect the chip to be in the power on / reset
            # state
            self.config_written = True
        else:
            if not self.config_written:
                write_config = self.configuration
                self.config_written = True
            else:
                write_config = None
        # if there is no difference between the configs simply return
        if write_config is None:
            return

        self.logger.debug(f"Sending string 'configure' to {self.hostname}:{self.port}")
        self.socket.send_string("configure")
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
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
        self.configuration = update_dict(self.configuration, write_config)

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


class TargetAdapter(ControlAdapter):
    """
    The adapter that is used to control the Targets (so ROCs and
    Hexboards) currrently uses the zmq_i2c server
    """

    def __init__(self, power_on_default: dict, initial_config: dict = None):
        try:
            hostname = power_on_default['hostname']
            port = power_on_default['port']
        except KeyError:
            if initial_config is not None:
                try:
                    hostname = initial_config['hostname']
                    port = initial_config['port']
                except KeyError as err:
                    raise DAQConfigError('A hostname and port are not '
                                         ' present in any configuration'
                                         ' received') from err
        super().__init__(power_on_default, hostname=hostname, port=port)
        if initial_config is not None:
            self.configure(initial_config)
        self.logger = logging.getLogger(
                'hexactrl_script.contol_adapter.TargetAdapter')

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
        msg = 'read'
        self.logger.debug(f"Sending string '{msg}' to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
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
        msg = 'read_pwr'
        self.logger.debug(f"Sending string '{msg}' to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
        pwr = yaml.safe_load(rep)
        return pwr

    def resettdc(self):
        msg = 'resettdc'
        self.logger.debug(f"Sending string '{msg}' to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
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
    Encapsulate the Access to the daq-client and server of the daq system.
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
        config, _, _ = self._filter_out_network_config(config)
        self.configuration = {self.variant_key_map[self.variant]: config}

    def configure(self, config: dict = None):
        """
        workaround for the way the zmq-client/zmq-server handles the
        configuration together with necessary checks for the
        """
        if config is not None:
            config, _, _ = self._filter_out_network_config(config)
            self.configuration = update_dict(
                    self.configuration,
                    {self.variant_key_map[self.variant]: config})
            self.config_written = False
        super().configure()

    def get_config(self):
        return self.configuration[self.variant_key_map[self.variant]]

    def start(self):
        """
        Start the aquisition of the data on the server and client
        """
        rep = ""
        while "running" not in rep.lower():
            msg = 'start'
            self.logger.debug(f"Sending string {msg} to {self.hostname}:{self.port}")
            self.socket.send_string(msg)
            rep = self.socket.recv_string()
            self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")

    def is_done(self):
        """
        check if the current aquisition is ongoing or not
        """
        msg = 'run_done'
        self.logger.debug(f"Sending string {msg} to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
        if "notdone" in rep:
            return False
        return True

    def stop(self):
        """
        stop the currently running measurement
        """
        msg = 'stop'
        self.logger.debug(f"Sending string {msg} to {self.hostname}:{self.port}")
        self.socket.send_string(msg)
        rep = self.socket.recv_string()
        self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")
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
            msg = 'delayscan'
            self.logger.debug(f"Sending string {msg} to {self.hostname}:{self.port}")
            self.socket.send_string(msg)
            rep = self.socket.recv_string()
            self.logger.debug(f"Received string '{rep}' from {self.hostname}:{self.port}")


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
        self.run_in_progress = False
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

    def __del__(self):
        self.tear_down_datat_taking_context()

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
        self.client.config_written = False
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

    def tear_down_datat_taking_context(self):
        """
        The complement to the 'start_run' function stops the run and cleans up
        after the run has completed
        """
        if os.path.exists(self.daq_data_folder):
            for file in self.daq_data_folder.iterdir():
                os.remove(file)
            os.rmdir(self.daq_data_folder)
