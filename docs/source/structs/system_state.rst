==============
The Task-State
==============

The ``task_state`` is the dictionary that contains all relevant information for the task to execute.
It may be modified by the parent task to appropriately shape the behaviour of the child task. Entries
are added and deleted from the dict as needed. This page lists and describes the entries of the System State
Dictionary.

**prioritize_daq** ``bool``
  Tells the worker tasks to run the daq part before starting to unpack the raw data. Defaults to ``False``
**name** ``string``
  Name of the procedure that the current task is part of. Only important for the ValveYard
**root_config_path** ``string``
  The path to the main configuration file (the one referenced on the command line)
**procedure** ``dict`` 
  The configuration of the procedure being run by the task. This is the config that is
  specified by the user.
**output_path** ``string``
  The path to the output directory of the Datenraffinerie. All data and analysis results
  are stored in this directory.
**analysis_path** ``string``
  Path to the directory containing the analysis python module.
**network_config** ``string``
  The path to the file containing the network configuration for that run
