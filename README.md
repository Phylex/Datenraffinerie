# Datenraffinerie

A tool to acquire and analyse HGCROCv3 Data for the HGCAL subdetector of the CMS at CERN.

To characterise the HGCROCv3 many measurements need to be acquired using different chip configurations. As the HGCROCv3 has built-in testing circuits
these are used for chip characterisation. The Datenraffinerie is a tool/framework that tries to simplify the execution of such data acquisition and
analysis tasks.

## Definition of the Terms used in this Document
- Target: The device/system that acquires the measurements and accepts the configuration. This can be either an LD/HD Hexaboard or a
Single-roc-tester. In future the Train might also be supported
- Procedure: A sequence of steps that are performed together and use a common configuration. Examples of procedures are daq-procedures that acquire
measurements from a target; analysis-procedures take the data acquired by daq-procedures and try to derive meaningful insights from that.
- Task: The smallest unit of a procedure. This term is taken from the library luigi used in this framework. A task produces a file at completion.
- Acquisition: The procedure that acquires data from the target also known as daq-procedure
- Analysis: An analysis takes data that was acquired during an acquisition and derives some sort of 'insight' from it. An 'insight' might be a plot or
the decision to keep/discard the chip that the data was acquired on.
- Distillery: Analyses are performed in 'Distilleries' which are the part of the datenraffinerie framework and provide the analysis code with the data
and the output directory where the analysis is expected to place it's outputs.

## Concepts
The Datenraffinerie expresses the Creation of plots as a sequence of two types of procedures. There is a DAQ procedure and an Analysis procedure.
A daq-procedure is expressed as a scan over a set of values of a configuration parameter of the target. If multiple target parameters are passed to an
acquisition procedure, it computes the Cartesian product of the parameters and performs a measurement for every target configuration from that set.
The daq-procedure is fully configurable, the daq-task structure is derived from a yaml configuration, more on that later.

Analyses derive useful information from the data provided by the acquisitions. The module that contains the Analysis code is loaded at runtime by the
datenraffinerie and does therefore not need to be aware of the context it is executed in. The context for the analysis code is also provided by `yaml`
configuration files in a similar format to the daq-configuration.

Data acquisition is performed by a target, that accepts some configuration and produces measurements where the it has configured itself and the HGCROCv3
chips that are part of it according to the configuration received. The Datenraffinerie computes the entire configuration of target and daq system 
for every measurement of the acquisition, guaranteeing that the system is in the desired state when taking data.
To be able to do this the user needs to provide a 'power-on default configuration' that describes the state of every parameter of the target at power on and the
configuration for the acquisition system.
parameters and scan ranges need to be provided by the acquisition configuration.\*

After computing the configuration for a single measurement from the aforementioned inputs the measurement is scheduled for execution on the target.
After the measurements have been acquired the data and configuration are merged into a single `hdf5` file that should contain all information needed.
The single hdf-5 file does not only contain data/configuration for a single measurement but for 
HDF-5 files can be loaded into pandas DataFrames using `pd.read_hdf('/path/to/file')`.

---
\*It may seem odd that the configuration for the entire chip is
computed for every measurement instead of changing only the parameter that is being scanned over. This needs to be done as every task is run in a
separate process and does not know when the luigi scheduler schedules it for execution. The order of measurements is not known and as such a task
cannot rely on a the configuration being in a predefined state, without creating that state itself.

---

## Execution Model
At the beginning of the Execution, the datenraffinerie is invoked by a cli command by the user. The user needs to provide some parameters to the
command to provide it with the location of the configuration to be used and the location at which to find the analysis code along with the name of the
procedure that the user wishes to execute and the location where the data needs to be written to.

The datenraffinerie then starts the ValveYard task. The job of the ValveYard is to parse the configuration provided by the user and schedule the
appropriate tasks with the luigi scheduler. The ValveYard reads in all configuration and then looks for an entry in the configuration that matches
with the name of the procedure that the user wishes to execute. Upon finding a matching entry it schedules either a `DistilleryAdapter` task (if the type of task is
`analysis` or a Scan task (if the type is `daq`). It uses the configuration of the user to determine the correct parameters to pass to either of the
tasks. At this point the initial call of the ValveYard returns, forcing the scheduler to schedule either the `Scan` or `DistilleryAdapter` task.

### Execution of a Scan and Measurement tasks
To tackle the problem of multi-dimensional scans, the `Scan` task uses recursion to keep the amount of code needed to perform a general
multi-dimensional scan small. The (simplified) input to a Scan task consists of a base configuration and a list of parameters and ranges to scan the
parameters over.
```python
Scan(base_target_configuration, [[param1, [0,1,2,3,...]], [param2, [0,2,4,5,...]]])
```
If the list of parameters to scan over is longer that one (which is the case in the previous example) it schedules a `Scan` task for each value of
`param1` to execute. To each of these `Scan` tasks it passes a copy of it's `base_target_config` where the `param1` of that copy was set to one of the
values that `param1` should be scanned over.

If the list of parameters is exactly one the `Scan` task Schedules the collection of tasks that together perform a single `Measurement` for every
value of the single parameter in the parameter list.

When a measurement is executed it checks if it needs a calibration to be present. If it is present it applies the calibrated values and preforms the
measurement (there is a bit more involved here but we shall get to that later). If a calibration is not present it is expected to be created by an
analysis (inside a distillery) and passed to the daq task.

### Execution of the Distillery task
