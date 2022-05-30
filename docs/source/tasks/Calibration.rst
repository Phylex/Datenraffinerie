The Calibration Task
====================

The calibration task is in charge of applying the calibration performed by the Calibration analysis specified in the configuration of the DAQ procedure
to the initial configuration of the DAQ procedure.

The Calibration task produces a single output, which is the accumulation of all previously performed calibrations applied the target as YAML file.
The Calibration then still needs to be applied to the actual target configuration but that is the responsibility of the DrillingRig and DataField tasks.


Requires
--------
ValveYard where the name is the procedure name of the Task that generates the Calibration overlay yaml file

Produces 
--------
Outputs a file that is the complete target configuration with initialization parameters and calibration overlayed on initial
The output is indicated to luigi as a dictionary with a ``full-calibration`` entry that contains the latest calibration file
