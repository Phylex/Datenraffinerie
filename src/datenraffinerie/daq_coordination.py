import zmq
import yaml
from pathlib import Path
from . import control_adapter as ctrl

def coordinate_daq_access(network_config: dict):
    """ a function run in a separate process that coordinates the access
    to the daq-system and target system so that the access is serialized
    and the daq interface is stabilized towards the datenraffinerie

    :network_config: the hostnames and ports of the target, daq-client and daq-server
    :returns: Nothing

    """
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{network_config['datenraffinerie_port']}")
    target = ctrl.TargetAdapter(network_config['target_hostname'],
                                network_config['target_port'])
    daq_system = ctrl.DAQSystem(network_config['daq_server']['hostname'],
                                network_config['daq_server']['port'],
                                network_config['daq_client']['hostname'],
                                network_config['daq_client']['port'])
    while True:
        message = socket.recv()
        message_delimiter = message.find(b';')
        command = message[:message_delimiter]
        if command == b'measure':
            if !target.has_default() and !daq_system.has_default():
                socket.send_string('error: no defaults loaded')
                continue
            config = yaml.safe_load(message[message_delimiter+1:].decode())
            daq_config = config['daq']
            target_config = config['target']
            target.configure(target_config, overlays_default=True)
            daq_system.configure(daq_config, overlays_default=True)
            measurement_data_path = Path('./measurement_data.raw')
            daq_system.take_data(measurement_data_path)
            with open(measurement_data_path, 'rb') as data_file:
                socket.send(data_file.read())
        elif command == b'load defaults':
            default_config = yaml.safe_load(message[message_delimiter+1:].decode())
            target_default_config = default_config['target']
            daq_default_config = default_config['daq']
            target.load_default_config(target_default_config)
            daq_system.load_default_config(daq_default_config)
            socket.send_string('defaults loaded')
        else:
            socket.send_string('invalid command')
