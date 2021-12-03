import zmq
import yaml
from time import sleep
from config_utilities import patch_configuration
from config_utilities import diff_dict


class DAQError(Exception):
    def __init__(self, message):
        self.message = message


class ControlAdapter:
    """
    Base class that encapsulates the configuration and communication to
    one of the daq-system components
    """

    def __init__(self, hostname, port, config):
        """
        Initialize the data structure on the control computer (the one
        coordinating everything) and connect to the system component.
        Do not load any configuraion yet
        """
        self.hostname = hostname
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
        self.confifguration = config

    def reset(self):
        """
        reset the connection with the system component, may not reset the
        state of the component
        """
        self.socket.close()
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")

    def configure(self, config):
        """
        send the configuration to the corresponding system component and wait
        for the configuration to be completed
        """
        config_diff = diff_dict(self.confifguration, config)
        # if there is no difference between the configs simply return
        if len(config_diff.items()) == 0:
            return
        self.socket.send_string("configure")
        rep = self.socket.recv_string()
        if "ready" not in rep.lower():
            raise ValueError(
                "The configuration cannot be "
                f" written to {self.hostname}. The target"
                f"responded with {rep}")
        self.socket.send_string(yaml.dump(config_diff))
        rep = self.socket.recv_string()


class TargetAdapter(ControlAdapter):
    """
    The adapter that is used to control the Targets (so ROCs and
    Hexboards)
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


class DAQSystem:
    """
    A class that abstracts encapsulates the interactions
    with the DAQ-system (the hexacontroller, hexaboard and zmq-[server|client])
    """

    def __init__(self, daq_config):
        # set up the server part of the daq system (zmq-server)
        self.server_config = daq_config['server']
        self.client_config = daq_config['client']
        # due to the way the zmq client works the files need to be written to
        # a temporary directory and then moved to the file expected by the DAQ
        # system
        clean_server_config = self._filter_out_network_config(
            self.server_config)
        self.server = DAQAdapter(self.server_config['hostname'],
                                 self.server_config['port'],
                                 clean_server_config)
        # set up the client part of the daq system (zmq-client)
        clean_client_config = self._filter_out_network_config(
            self.client_config)
        self.client = DAQAdapter(self.client_config['hostname'],
                                 self.client_config['port'],
                                 clean_client_config)

    def configure(self, daq_config=None):
        """
        configure the daq system before starting a data-taking run
        """
        if not self.server.is_done():
            raise DAQError("DAQ system is running, it should not be")
        self.server.stop()
        self.client.stop()
        if daq_config is not None:
            server_config = self._filter_out_network_config(
                daq_config['server'])
            client_config = self._filter_out_network_config(
                daq_config['client'])
        else:
            server_config = self._filter_out_network_config(
                self.server_config)
            client_config = self._filter_out_network_config(
                self.client_config)
        self.client.configure(client_config)
        self.server.configure(server_config)

    def take_data(self, output_data_path):
        pass

    @staticmethod
    def _filter_out_network_config(config):
        """
        As there is minimal network configuration inside the daq system config
        we need to filter this out to be able to pass along the parameters that
        are intended for the actual server and client
        """
        out_config = {}
        for k, v in config.items():
            if ('hostname' not in k) and ('port' not in k):
                out_config[k] = v
        return out_config
