from daq_transports import ZMQ_control_transport
from daq_protocols import Hexaboard_Target_Protocol, Hexcontroller_DAQ_Protocol
from config_cache import ConfigCache
import copy


class HexaboardBackend(object):
    def __init__(self, hostname: str, port: str, default_config: dict):
        transport = ZMQ_control_transport(hostname, port)
        self.protocol = Hexaboard_Target_Protocol(transport)
        self.cache = ConfigCache()
        self.cache.set_default(default_config)

    @property
    def configuration(self):
        """The configuration property."""
        return copy.deepcopy(self.cache.cache)

    @configuration.setter
    def configuration(self, value):
        self._configuration = value


class HexacontrollerBackend(object):
    def __init__(self, hostname, port, default_config: dict):
        transport = ZMQ_control_transport(hostname, port)
        self.protocol = Hexcontroller_DAQ_Protocol(transport)
        self.cache = ConfigCache()
        self.cache.set_default(default_config)

    @property
    def configuration(self):
        """The configuration property."""
        return copy.deepcopy(self.cache.cache)

    @configuration.setter
    def configuration(self, value):
        config, _, _ = filter_out_network_config(value)
        write_config = self.cache.cache_write(config)
        self.protocol.write(write_config)


def filter_out_network_config(config):
    """
    As there is minimal network configuration inside the daq system config
    we need to filter this out to be able to pass along the parameters that
    are intended for the actual server and client

    Also has to handle data weirdly because of technical debt in the daq
    c++ software
    """
    if config is None:
        return None
    # this weird contraption needs to be build because the current zmq
    # server and client expect the ENTIRE configuration (includig
    # hexaboard and every other component to be sent to them
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
