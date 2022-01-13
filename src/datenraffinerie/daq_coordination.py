from . import control_adapter as ctrl

def coordinate_daq_access(initial_target_config: dict,
                          initial_daq_system_config: dict,
                          datenraffinerie_port: int):
    """ a function run in a separate process that coordinates the access
    to the daq-system and target system so that the access is serialized
    and the daq interface is stabilized towards the datenraffinerie

    :initial_configuration: The initial configuration for the 
    :datenraffinerie_port: the port via the Measurement processes communicate
        with the daq_coordinator.
    :returns: Nothing

    """
    target = ctrl.TargetAdapter(initial_target_config)
    daq_system = ctrl.DAQSystem(initial_daq_system_config)
