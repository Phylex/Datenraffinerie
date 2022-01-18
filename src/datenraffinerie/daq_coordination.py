import zmq
import yaml
from . import control_adapter as ctrl

def coordinate_daq_access(default_target_config: dict,
                          default_daq_system_config: dict,
                          datenraffinerie_port: int):
    """ a function run in a separate process that coordinates the access
    to the daq-system and target system so that the access is serialized
    and the daq interface is stabilized towards the datenraffinerie

    :initial_configuration: The initial configuration for the 
    :datenraffinerie_port: the port via the Measurement processes communicate
        with the daq_coordinator.
    :returns: Nothing

    """
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f"tcp://*:{datenraffinerie_port}")
    target = ctrl.TargetAdapter(default_target_config)
    daq_system = ctrl.DAQSystem(default_daq_system_config)
    while True:
        message = socket.recv()
        c = message.find(b';')
        command = message[:c]
        if command == b'measure':
            config = yaml.safe_load(message[c+1:])
            daq_config = config['daq-system']
            target_config = config['target-system']
            target.configure(target_config)
            daq_system.configure(daq_config)
            socket.send_string(f"done")
