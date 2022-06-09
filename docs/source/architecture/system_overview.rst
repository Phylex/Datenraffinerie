============================
System architecture Overview
============================

The Datenraffinerie is a parallel, architecture designed to scale to multi core systems easily

As the Datenraffinerie uses the luigi library to schedule tasks that make the Datenraffinerie parallel
it inherits the core aspects of luigi.

1. Build the dependency tree of all the tasks

2. Depending on the priority of the tasks without dependencies, schedule the tasks for execution on one of potentially
   many workers

3. Execute the scheduled tasks until the root of the task tree and all of it's dependencies have been completed

The Datenraffinerie uses the luigi tasks to perform its purpose of aquiring and analysing data from the HGCAL detector test systems.
There are three tasks that make up the core of the Datenraffinerie:

1. The ValveYard task has the job of reading in and parsing and validating the user and system configuration and scheduling the other tasks
   based on the user supplied configuration.

2. The Well task that is responsible for acquiring data from the target system

3. The Distillery task that is responsible for loading and running the user supplied Analyses

-----

The Tasks
=========

The ValveYard Task
------------------
The :doc:`ValveYard </tasks/valveyard>` task is responsible for parsing and validating the configuration. It does this by starting from the user supplied main config file, that is passed to The
Datenraffinerie via the command line. after loading and validating the configuration found ther (assuming all files exist and the configuration is valid)
the ValveYard runs the detected procedures in the order they where specified (multiple procedures can be specified at a time). This is done by specifying the priority of the 
procedure that is declared as dependency.


The Well Task
-------------
The :doc:`Well </tasks/well>` task is at the core of the DAQ procedure. It makes sure that the DAQ procedure is executed correctly. This is done in two stages.
The upper stage is the task that is depende  upon by the ValveYard, that declared the Well as a dependency in response to a daq procedure
needing to be executed. This stage of the Well task is in charge of merging the output (if configured) into a single ``hdf5`` file and distributing the 
workload among the available worker processes. The lower stage of the Well task is responsible for aquiring the data from the target system and
transforming it into the ``hdf5`` file format containing a table with the user specified data and configuration columns in it.


The Distillery Task
-------------------
The :doc:`Distillery </tasks/distillery>` task is responsible for loading and executing the user provided analysis. It's purpose is to find an analysis class that matches the one specified in the 
configuration and execute it so that it integrates into the Datenraffinerie.

----

Data structures
===============


The Task-State
--------------
As it is possible that a ValveYard declares either a distillery or a well as it's dependency and both distillery and well can in turn declare a ValveYard as their dependency
The flow of information needs to be managed. To do this a data structure the :doc:`task state </architecture/system_state>` is used. It provides a container for all the information needed
by the a task and is adapted by the parent task to contain the correct information for the child classes to function properly.


The User configuration
----------------------
The user configuration is provided by the user and must contain all necessary information for the Datenraffinerie to function properly. It is validated by the ValveYard and generally split
into three parts.

1. The :doc:`main configuration file</usage/main_config>`: binds all other configurations together. It can include 'library files' that may define procedures. It can also declare it's own procedures in 
   it's ``procedures`` section. 

2. The :doc:`daq procedures file </usage/daq-procedure-configuration>`: this is a library file containing mostly/only configuration entries for daq procedures.

3. The :doc:`analysis procedures file</usage/analysis-procedure-configuration>`: This, like the daq procedures file is a file that containes mosly/only configuration entries for analysis procedures.
