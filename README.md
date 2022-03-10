# Datenraffinerie

A tool to acquire and analyse HGCROCv3 Data for the HGCAL subdetector of the CMS at CERN.

To characterise the HGCROCv3 many measurements need to be acquired using different chip configurations. As the HGCROCv3 has built-in testing circuits
these are used for chip characterisation. The Datenraffinerie is a tool/framework that tries to simplify the execution of such data acquisition and
analysis tasks.

## Definition of the Terms used in this Document
- Target: The device/system that acquires the measurements and accepts the configuration. This can be either an LD/HD Hexaboard or a
Single-roc-tester. In future the Train might also be supported.
- backend: The combination of both the daq system and the Target.
- Procedure: A sequence of steps that are performed together and use a common configuration. Examples of procedures are daq-procedures that acquire
measurements from a target; analysis-procedures take the data acquired by daq-procedures and try to derive meaningful insights from that.
- Task: The smallest unit of a procedure. This term is taken from the library luigi used in this framework. A task produces a file at completion.
- Acquisition: The procedure that acquires data from the target also known as daq-procedure
- Analysis: An analysis takes data that was acquired during an acquisition and derives some sort of 'insight' from it. An 'insight' might be a plot or
the decision to keep/discard the chip that the data was acquired on.
- Distillery: Analyses are performed in 'Distilleries' which are the part of the datenraffinerie framework and provide the analysis code with the data
and the output directory where the analysis is expected to place it's outputs.

## Installation
### PyPi
The Datenraffinerie is available on pypi. This means that it can be installed via pip. To be able to use the datenraffine Python 3.9 is needed. Python 2
is _not_ supported. It is recommended that a python virtual environment is used for installation. Python 3.9 can be installed on centos7 by compiling
from source. To set up a python environment run:
```
$ python3.9 -m venv venv
```
this creates a [virtual environment](https://docs.python.org/3/library/venv.html). in the `./venv` directory. The virtual environment can be activated by running
```
$ source ./venv/bin/activate
```
in a bash shell.
To deactivate the virtual environment, run:
```
$ deactivate
```

In the virtual environment simply install the datenraffinerie via pip with the command
```
pip install datenraffinerie
```
This will install the latest version released on the [python package index](https://pypi.org/project/datenraffinerie/).


### from Source
To install the datenraffinerie it is assumed that python 3.9 is available and is executed via the `python` shell command.
To install the datenraffinerie from the git repository clone the repository and then change the working directory to the root of the git repository
then initialize a virtual environment as shown in [PyPi](#PyPi). Then activate the virtual environment and run the command
```
$ pip install .
```
This should install all needed runtime requirements for and datenraffinerie itself.

## Running Datenraffinerie
After the installation the command `datenraffinerie` is available.
To find out about the options of the command line tool run:
```
$ datenraffinerie --help
```

To get going with the Datenraffinerie, network configuration and a daq/analysis configuration is needed. Examples for these Configurations can be found
in the `examples` directory of the git repository. Further Configurations can be found in the.
`tests/configuration` directories of the repository. See [configuration](#Configuration) for more details.

When using custom analysis code, the location of the module that provides this code has to be specified with the `-a` option. An example of custom
analysis code can be found in `examples/example_analysis_collection`.

As the Datenraffinerie was designed for the use of parallel processes, it is capable of running multiple procedures in parallel. The amount of
parallel tasks can be specified by setting the number of `workers` with the `-w` option. The default for this option is 1, so without setting
this value explicitly it will not run in parallel.

## Concepts
The Datenraffinerie expresses the Creation of plots as a sequence of two types of procedures. There is a DAQ procedure and an Analysis procedure.
A daq-procedure acquires data from the target system. As most Measurements are scans of a multi dimensional phase space, the daq system was designed
to make these kind of phase space scans as easy as possible. A daq procedure that is configured with a list of multiple parameter scans will combine
them into a Cartesian product of the parameters and performs a measurement for every target configuration from that Cartesian product space.
The daq-procedure is fully configurable, the daq-task structure is derived from a yaml configuration, see [configuratoin](#Configuration) for details.

Analyses (also called Distilleries in the context of the Datenraffinerie) derive useful information from the data provided by the acquisitions.
The module that contains the Analysis code is loaded at runtime by the Datenraffinerie and is desigend to run custom analysis code, see [writing a custom Distillery](#Writing a custom Distillery).
If the custom distillery needs any sort of configuration it can be specified in the corresponding analysis
configuration. The configuration is in a very similar format to the configuration of the daq system and provided as a yaml file.

Data acquisition is performed by a target, that accepts some configuration and produces measurements where the it has configured itself and the HGCROCv3
chips that are part of it according to the configuration received. The Datenraffinerie computes the entire configuration of target and daq system 
for every measurement of the acquisition, guaranteeing that the system is in the desired state when taking data.
To be able to do this the user needs to provide a 'power-on default configuration' that describes the state of every parameter of the target at power on and the
configuration for the acquisition system.

After computing the configuration for a single measurement from the daq configuration the measurement is scheduled for execution on the target.
After the measurements have been acquired the data and configuration are merged into a single `hdf5` file that should contain all information of the
scan.
The resulting data does not only contain the data received from all the individual measurements, but also the relevant configuration for every
channel of every measurement. This gives the Distillery (anlysis) developer the freedom to slice and filter the data to their relevant needs. It also
means that the data format for every analysis is identical. Furthermore the Data is provided to the analysis as a pandas `DataFrame` giving the
analysis developer a modern and extensive set of tools to work with. For a close look at the data format see the [Data Format](#Data Format) section.

## Execution Model
The execution model of the Datenraffinerie relies on the same execution model of the [luigi](https://github.com/spotify/luigi) library that is used by
the Datenraffinerie. As such the Datenraffinerie constructs a dependency graph of tasks before executing them. Task `A` that is depended upon by task `B`
is run before task `B`. However during creation of the dependency graph task `B` is queried for it's dependencies before task `A` is, as any task is
only run if it is depended upon by another.

At the beginning of the Execution, the Datenraffinerie is invoked through a command line interface (CLI) by the user. The user needs to provide some parameters to the
command to provide it with the location of the configuration to be used and the location at which to find the analysis code along with the name of the
procedure that the user wishes to execute and the location where the data needs to be written to.

To begin with the configuration files that where passed in by the user need to be parsed and the procedure that is to be executed found. This is done
in the `ValveYard` class. After parsing the configuration, the `ValveYard` declares that it depends upon the Task that was indicated by the user
during invocation.

The `ValveYard` can declare two types of dependencies, either the dependency is of type `daq` or of type `analysis`. As the Analysis will always
require some data it in turn declares a dependency upon the `ValveYard` task but this time the Analysis acts as the user, indicating a `daq` type task
to be searched for and subsequently depended upon by the new instantiation of the `ValveYard` class.

![Invocation of the valveyard](docs/valveyard-invocation.svg)

### DAQ type procedures
In contrast to the `analysis` type tasks discussed previously that rely on external code to run, and usually consist of a single task, the DAQ
procedure is entirely implemented in the Datenraffinerie and relies on a recursive task called `DataField` to be able to generate the Cartesian product of
the parameters specified by the user configuration. In the simplest case the `DataField` task does not recurs and directly starts a set of measurement tasks

![non recursive scan](docs/daq-task-dependency-graph-1D.svg)

If mutiple parameter ranges are passed to the `DataField` task during the creation of the dependency graph it will not directly declare measurements as
it's dependency but instead declare a set of `DataField` tasks as it's dependency, one for every value of the 'dimension' it is supposed to scan over.
This is probably best visualized as in the following picture:

![recursive scan](docs/daq-task-dependency-graph-3D.svg)

The bottom level of this tree is made up of the actual measurements. In the case of a simple scan without the need for a calibration, the Measurements
are the final node in the dependency graph. As the computation of the dependency graph is now complete the tasks are now actually executed.
During execution, the measurement calculates the final measurement configuration and send it to the
`daq_coordinator` which is in charge of managing the access to the measurement system for more on that see [The `daq_coordinator`](#DAQ Coordination).

#### Alternate DAQ behaviour

Along with the above mentioned execution mode, the `DataField` can be configured to acquire the data itself without spawning `DrillingRig`s to each
acquire a single run. It performs the acquisition tasks in a loop before passing the raw data to the `Fracker` that processes the data into the
DataFrames that are ultimately passed to the `Distillery`s. In this Mode the DAQ and the data processing are entirely decoupled. The Processing of the
raw data will only start to commence after all the data has been gathered from the chip. To put the Datenraffinerie into this mode the `-l` option has
to be passed to the Datenraffinerie on the command line.

## Configuration
To get the Datenraffinerie to work properly, it needs to be configured. As mentioned earlier, there are examples of the configuration available in the
`examples` and `tests/configuration` directory of the git repository. The configuration is a list of procedures that can be spread over multiple files
for the purpose of structuring/segmenting different types of procedures, production vs. development for example. All files use the yaml syntax, for a
detailed explanation of it's syntax see [here](https://yaml.org).
The different files are all tied together into in the 'main' configuration file. The main configuration file in contrast to every other file does not
represent a list on the top level but instead a dictionary. An example of a main configuration file is given below:

```yaml
libraries:
  - "./daq_procedures.yaml"
  - "./analysis_procedures.yaml"
```

As can be seen, the main configuration simply includes different files that contain the actual procedures available for use with the datenraffinerie.
This file needs to be specified by the user during invocation of the Datenraffinerie using the CLI. The paths in the main configuration and in any
other configuration file are assumed to be relative to the location of the file they are occurring in. Next we shall take a look at the configuration
of the Analysis and DAQ procedure.

### Configuration of the Analysis Procedure
The Distillery configuration is the simpler of both configurations from the point of view of the datenraffinerie, They can become quite complex
depending on the needs of the analysis run by the Distillery. An example of an Distillery configuration follows:

```yaml
- name: my_analysis
  type: analysis
  python_module_name: my_analysis_import_name
  daq: my_daq_procedure
  parameters:
    p1: 346045
    p2: 45346
    p3: 'string option'
```

As can be seen in the example, the Analysis procedure is an entry in a list. A file that is included in the main configuration must be a yaml representation of a list.
The above example may be one of possibly many entries in a file. Every entry needs the `name` field as it is the name by which the `Valve Yard` identifies the
procedure to be executed. The value of the `name` field is also the value that the user specifies on the command line to tell the Datenraffinerie what
procedure to execute.

Also mandatory for every entry is the `type` field. It defines if it is an Analysis or a DAQ procedure.
In the case of an Analysis, It is necessary to declare the daq procedure to collect the neede information to be able to perform the analysis.
This is done with the name specified in the `daq` field. The name specified here needs to match with the `name` field of the daq procedure.

As the code for the Analysis is loaded by the Distillery at runtime, the Distillery needs to know the name of the module to be
imported. That name is specified in the `python_module_name` field. The name needs to match the name given to the analysis class in the `__init__.py` file
of the analysis collection. Using the above configuration as an example, the following line would need to appear in the `__init__.py` file of the analysis collection:
```
from . import MyCustomAnalysis as my_analysis_import_name
```
This assumes, that the Class containing the analysis code is called `MyCustomAnalysis`.

The parameters field is where the parameters for the analysis can be specified. It is assumed to be a dictionary and the entries in the 'parameters'
dictionary are passed as a dictionary to the custom analysis code by the Distillery class. So given the above example the Analysis would be passed
```python
{
    p1: 346045,
    p2: 45346,
    p3: 'string option
}
```

For more details see [here](#Writing a custom Distillery)

### Configuration of the DAQ Procedure
The configuration of the DAQ Procedure is more complicated as it needs to define everything needed to calculate the entire system state for every
measurement performed during the acquisition.
```yaml
- name: timewalk_scan
  type: daq
  event_mode: false
  target_settings:
    power_on_default: ./defaults/V3LDHexaboard-poweron-default.yaml
    initial_config: ./init_timewalk_scan.yaml
  daq_settings:
    default: ./defaults/daq-system-config.yaml
    server_override:
      NEvents: 1000
      l1a_generator_settings: # type can be 'L1A', 'L1A_NZS', 'CALPULINT' and 'EXTPULSE0' ; followMode can be DISABLE, A, B, C or D 
      - {name: 'A', enable : 1, BX : 16, length : 1, flavor: CALPULINT, prescale : 0x0, followMode : DISABLE}
      - {name: 'B', enable : 0, BX : 38, length : 1, flavor : L1A, prescale : 0x0, followMode : A}
      - {name: 'C', enable : 0, BX : 0x30, length : 1, flavor : L1A, prescale : 0x0, followMode : DISABLE}
      - {name: 'D', enable : 0, BX : 0x40, length : 1, flavor : L1A, prescale : 0x0, followMode : DISABLE}
  parameters:
    - key:
      - target
      - ['roc_s0', 'roc_s1', 'roc_s2']
      - 'ReferenceVoltage'
      - [0, 1]
      - 'Calib'
      range:
        start: 0
        stop: 2048
        step: 32
    - key:
      - daq
      - l1a_generator
      values:
        - {'special': 'value'}
        - {'special': 'val2'}
  data_columns:
    - chip
    - channel
    - channeltype
    - HighRange
    - LowRange
    - Calib
    - phase_strobe
```

Just as with the analysis procedure the `name` and `type` fields are present, specifying the name of the procedure as specified by the user and
it's type, indicating if it is a daq or analysis procedure.

The configuration is split into three sections the `target_settings` section that defines the default and initial settings for the target, the
`daq_settings` section that describe the configuration of the daq server and client and the parameters section that describes the parameters defining
the axes of the 'phase space' that is scanned over.

Both parameters of the target and daq system can be referenced in a scan. To select a parameter from the target system to scan over, the first entry
of the `key` Field needs to be set to `target`, this is done in the first entry of the `parameters` field.
To scan over a `daq` parameter, the first entry of the key field needs to be `daq`. If the first entry in the `key` parameter is neither `daq` or
`target`, a `target` is automatically prepended. This was done to keep it backwards compatible with existing scan configurations. The automatic
prefixing is considered  temporary feature and will be removed in a future release.

Instead of providing a simple numerical range, it is also possible to specify individual values that should be scanned over. The values can be
complex dictionary/lists structs. This makes single value scans with non numerical values possible. An example is shown in the second scan parameter
of the above example.

The columns of data that end up in the resulting DataFrame can now also be selected by specifying the optional `data_columns` list. If `data_columns`
is not provided all available columns are written into the output DataFrame. If a column specified in the `data_columns` list is not found in the set
of available columns it is simply ignored.

### Target Settings
The `target_settings` section has two parts, the first is the `power_on_default` section.

The `power_on_default` field sets the path to a yaml file that describes the configuration of the target after either a reset or a power on.
It is used to calculate the parameters that actually need to be sent to the backend and avoid unnecessary writes. There is generally one
file per test system used.

The `initial_config` specifies the set of parameters that differ from the power on configuration for the target. They do not need to provide the
values of the parameter being scanned over but can contain an initial value for them (it will however be overwritten). This file sets the parameters
that are specific to each daq procedure.

### DAQ Settings
The `daq_settings` section specifies the settings of the DAQ system. It is assumed that the DAQ settings do not change between Measurments of the same
procedure. There is one field and there are two subsections in the `daq_settings` section. The `default` field is the path to the default settings of the
daq system. The default settings only need to change if the the zmq-server and zmq-client C++ Programs running on the Hexacontroller are updated and
end up using use a different configuration interface.

The two sections, of which only one of them is shown in the above example specify overrides to the `daq_settings`.
These are the `client_override` and `server_override` sections. These sections specify parameters that need to be set to non default values of the DAQ system
in order for it to work with the scan that is to be performed. As it is assumed that
these settings may vary from scan to scan the non-default settings are made explicit for every DAQ procedure.

### Parameters
The parameters section describes the parameters that need to be adjusted from one measurement/run to the
next. `parameters` is a list of dictionaries. Every entry of this list has the same structure. There is a `key` field that describes what parameter
of the targert needs to be changed from one measurement to the next and the range field that describes the different values the parameter needs to be
set to. Please see [key generation](#Key generation) for more details.
If multiple entries are specified, a measurement is performed for every element of the Cartesian product of both ranges.

#### Key generation
It is assumed that the Target configuration essentially mirrors the parameters and hierarchy of the slow control parameters of the HGCROC. If a system
consists of multiple ROCs the configuration of each roc becomes a subdicitonary with the key being the name of the HGCROC.
To understand how the actual parameter is computed an example of the `key` as it appears in the daq-procedure configuration and the resulting dictionary
that is set to a value specified in the `range`
field is given:
```yaml
key:
  - ['roc_s0', 'roc_s1', 'roc_s2']
  - 'ReferenceVoltage'
  - [0, 1]
  - 'Calib'
range
  start: 0
  stop: 33
  step: 32
```
results in the following keys being generated. Once with the value 0 as show here and once for the value 32.
```yaml
roc_s0:
  ReferenceVoltage:
    0:
      Calib: 0
    1:
      Calib: 0
roc_s1:
  ReferenceVoltage:
    0:
      Calib: 32
    1:
      Calib: 32
roc_s2:
  ReferenceVoltage:
    0:
      Calib: 32
    1:
      Calib: 32
```
In the above example the Measurement that is being performed has assigned the value specified by the key to `32`. In a different measurement task it
would be set to a different value, for example `64`.

## Data Format
The Data that is generated by the DAQ procedures of the Datenraffinerie always has the same format, independent of the daq procedure run. All data is
contained in the pandas `DataFrame` passed to the Analysis code. The configuration information of the chip is included in the file as additional
columns.

Each row represents a single channel during a single measurement. As configuration parameters change from one measurement to the next the columns
holding the corresponding configuration parameter will reflect this.

The HGCROC has channel wise and global parameters. Every row of the `DataFrame` will therefore contain the configuration of that specific channel,
reflecting the channel specific configuration. It will also contain all global fields of the chip configuration. This allows the Analysis code to
simply select the data of interest without the need to know how the data was acquired (assuming of course that the relevant selection is contained in
the `DataFrame` provided by the daq procedure). Every `DataFrame` will contain the same columns, the contents of the data depends of course on the daq
procedure specified in the configuration.

To illustrate the point here is the data format for a simplified measurement. The Chip A has the following configuration:
```yaml
global:
  ADC_gain: 1
  DAC_gain: 2
ch:
  0:
    connected: 1
	threshold: 2
  1:
    connected: 0
	threshold: 0
  2:
    connected: 1
	thershold: 2
  3:
    connected: 0
	threshold: 0
```

A measurement yields an `adc_val` and the daq procedure specifies a scan of the threshold of the channels. As can be seen, channels 1 and 3 are not
connected. 5 measurements are taken. If an `adc_val` is below threshold, the Chip sets the value to 0. A disconnected Channel also will show an
`adc_val` of 0. Given the previous assumptions a measurement may look like:

| channel | adc_val | ADC_gain | DAC_gain | connected | theshold |
|---------|---------|----------|----------|-----------|----------|
|0|12|1|2|1|2|
|1|0|1|2|0|0|
|2|12|1|2|1|2|
|3|0|1|2|0|0|
|0|13|1|2|1|4|
|1|0|1|2|0|0|
|2|11|1|2|1|4|
|3|0|1|2|0|0|
|0|9|1|2|1|6|
|1|0|1|2|0|0|
|2|13|1|2|1|6|
|3|0|1|2|0|0|
|0|0|1|2|1|8|
|1|0|1|2|0|0|
|2|10|1|2|1|8|
|3|0|1|2|0|0|
|0|11|1|2|1|10|
|1|0|1|2|0|0|
|2|11|1|2|1|10|
|3|0|1|2|0|0|
|0|13|1|2|1|12|
|1|0|1|2|0|0|
|2|0|1|2|1|12|
|3|0|1|2|0|0|

There are roughly 200 columns in the `DataFrame` so they will not be listed here. A list of the columns can be obtained with the
`pd.DataFrame.columns` member.

To limit the amount of columns in the output DataFrame to only the columns needed by the analysis they can be specified in the `data_columns` list of
the daq configuration

### Selecting columns in the output DataFrame


## Writing a custom Distillery
Writing a custom distillery is neccessary to produce Plots and other useful information (like a summary or calibration parameters) from data aquired by the daq system.
Distilleries are executed by the Datenraffinerie after aquiring the neccesary data. Distilleries like the DAQ procedures are only run, if the output
of the procedure is not already present.

A distillery is a python class without inheritance. The class needs to have three methods `__init__(self, parameters)` to initialize the class with
the parameters from the analysis configuration, an `output(self, output_dir)` method that specifies the files that are produced by the Distillery and
a `run(self, data)` method that is called to process the data gathered by the daq procedure.

A minimal example that produces a single empty file `summary.csv` as output and ignores the data passed to it in the run method would be:
```python
from pathlib import Path

class MyLittleDistillery(object):
    def __init__(self, paramerets):
        self._params = parameters

    def output(self):
        return {
            'summary': 'summary.csv',
            'plots': [],
            'calibration': None
        }

    def run(self, data, output_dir):
        op = Path(output_dir)
        (op / self.output()['summary']).touch()
```

### Discovery of custom analyses
The datenraffinerie needs to find the custom Distilleries to execute them. To make this possible, the different distilleries used must be placed
together into a folder. along with the python files for the distillery/distilleries the directory must contian a `__init__.py` file. This turns the
folder into a python module that can be imported by the datenraffinerie. During the import of a module the instructions in the `__init__.py` file
are executed. So that the custom distillery can be found a line must be added into the `__init__.py` file. Assuming that the configuration for the
analysis has the following setting:
```
python_module_name: example_analysis_class
```
and we are trying to make the `MyLittleDistillery` executable by the datenraffinerie and the `MyLittleDistillery` is located in
`my_little_distillery.py`, then the line in `__init__.py` needs to be:
```
from my_little_distillery import MyLittleDistillery as example_analysis_class
```

### Different Input Formats
The daq procedures can be run in `event_mode` or in `summary_mode`. In `summary_mode` the raw data is processed into aggregates together with
statistical information.

The `summary_mode` is the default if the `event_mode` configuration parameter is either not set or set to `False`. in summary mode the analysis
receives a pre loaded pandas `DataFrame` as `data` argument of the `run` function.

In `event_mode` every event that was recorded is listed in the output_data. This makes the loading the whole data into
memmory unfeasable (Data files that are decompressed and loaded into memmory have sizes in the hundreds of Gigabytes). To mitigate this effect the
pandas `HDFStore` object is utilized to open the file without loading the all the data into memmory. The `HDFStore` object is then passed to the
`run` method instead of the dataframe. The `HDFStore` has a
[select](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.HDFStore.select.html) method that can be used to query the properties of
the data and load sections of data into main memmory that are needed by the analysis. Due to the structure of the HDF5 file, it is currently not
possible to load the data as an iterator. Filters or the start/stop arguments can be used to successively load only a subset of all rows into main
memmory. Please see the [pandas documentation](https://pandas.pydata.org/pandas-docs/stable/index.html) for more details.
The underying file is opened in `read only` mode so the modifications made to the data loaded into memmory do not have an effect on the underlying
file. Please keep in mind that the only files that are allowed to be created by an analysis/Distillery are the files specified in the `output(self)`
method of the Distillery.
