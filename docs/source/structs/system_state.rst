The System State
================

The system state is the dictionary that contains all relevant information for each and every process of the 
tree. It may be modified by the parent task to appropriately shape the behaviour of the child task. Entries
are added and deleted from the dict as needed. This page lists and describes the entries of the System State
Dictionary.
* ``loop``: ``bool``: This entry tells the DataField that the lowest dimension of the scan should be 
  unroled and performed in the same task. This speeds up the data aquisition but reduces parallellism.
* ``name``: ``string``: Name of the procedure that the current task is part of.
* ``root_config_path``: ``string``: The path to the main configuration file (the one referenced on the command line)
* ``procedure``: ``dict``: The configuration of the procedure being run by the task. This is the config that is
  specified by the user. It also contains the config of the Target and daq system and so can become quite large
  The Different tasks will alter the configuration in this section to provide the right info to the subtasks
* ``event_mode``: ``bool``: This flag determins how the data gathered is unpacked and formatted.
* ``output_path``: ``string``: The path to the output directory of the Datenraffinerie. All data and analysis results
  are stored in this directory.
* ``analysis_path``: ``string``: Path to the directory containing the analysis python module.
* ``network_config``: ``string``: The path to the file containing the network configuration for that run
* ``event_mode``: ``bool``: Indicates if the data processed by the Datenraffinerie is summary data or event by event data
