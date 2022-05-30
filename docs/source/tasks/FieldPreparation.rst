FieldPreparation
================
The FieldPreparation task makes sure that the ROCs and DAQ system are properly initialized by sending a ``load_defaults``
command to the ``daq_coordinator`` so that it in turn initializes the rocs and resets it's caches to the initial state.

If the connection to the daq_coordinator can not be established it times out and produces an error
