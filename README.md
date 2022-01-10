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

## Concepts
Data acquisition is performed by a target, that accepts some configuration and produces measurements where the HGCROCv3 along with other target
systems have been configured according to the configuration received. The Datenraffinerie computes the configuration for every measurement of the
acquisition. To do this the user needs to provide a 'power-on default configuration' that describes the state of every register of the device at power
on and the configuration for the acquisition to be performed. An acquisition normally consists of a scan of one or more chip parameters. The
parameters and scan ranges need to be provided by the acquisition configuration.

After computing the configuration for a single measurement from the aforementioned inputs the measurement is scheduled for execution on the target.
After the measurements have been acquired the data and configuration are merged into a single `hdf5` file that should contain all information needed.
The single hdf-5 file does not only contain data/configuration for a single measurement but for 
HDF-5 files can be loaded into pandas DataFrames using `pd.read_hdf('/path/to/file')`.




## Folder Structure
A measurement is usually conducted with a chip or board as it's target. A Measurement may require Analyses and/or calibrations to be performed.
Running a measurement will create the following folder structure
```
Target
├── Calibration
├── Measurements
└── Analyses
```
The `Target` name will be specified by the user as a command line argument when launching a workflow. If the `Target` folder does not exist it will be
created along with the subfolders for the three stages. The subfolder for each stage will in turn have one folder for a variant of that stage.
So if three different calibrations have been performed on the target `ROCv3-539345` then the following folder structure will be
```
ROCv3-539345
├── Calibration
│   ├── adc
│   ├── pedestal
│   └── toa-acg
├── Measurements
└── Analyses
```
The same rules apply to the Measurement and Analyses folders.

### Handling of intermediate files
Every stage of the measurement, calibration and Analysis procedure may produce intermediate files, as a means of moving data from one task to the
next. To avoid clutter and duplicate or even contradicting information these files SHOULD NOT be placed in the above folder structure.
Intermediate files may be placed in the `/tmp` directory of the filesystem if needed.

### Idempotency of Stages
As no intermediate information is stored in the Folder the tasks that perform Calibration and Analysis must produce the same result when run with the
same data. This is what is meant with idempotency. Thus if Data for a Target has been taken once, a new measurement of the same data should not be needed.

---
## Keeping Track of State
Beside the raw data taken from the target, other information like the state of the targets slow-control  and it's environment are important to contextualize the
measurements. Depending on the amount of change expected for these parameters there may be 2 different types of state tracking files, one that defines
the state of the system/environment for one stage and one that defines the state/environment for every 'atomic' data-taking step.

### Keeping Track of slow changing State
Things like temperature or humidity might affect the operation/calibration/performance of the target. These variables, when controlled for, tend not
to change quickly. Therefore these would be recorded once for every execution of a stage. There could, for example be a calibration for the pedestals
at -30C and at +25C. As such there would be one folder inside the pedestal folder of the Calibration stage.
```
ROCv3-539345
├── Calibration
│   ├── adc
│   │   ├── 1
│   │   └── 2
│   ├── pedestal
│   └── toa-acg
├── Measurements
└── Analyses
```

After successful execution of two `adc` calibrations with different environmental conditions there would be two folders inside the `adc` folder of the
calibration stage as shown above. Each of these directories will contain two top-level files, one corresponding to the calibration overlay that calibrates
the different slow control parameters of the target, named `calibration_overlay.yaml` and one that contains the state of the environment during the
execution called `environment.yaml`. The concept of the environment should also include settings of the Target that do not vary for an entire
measurement, but may vary from one measurement to the next.

### Taking new data if the environment is different
When a Stage is executed, environmental information in form of a `*.yaml` file may be passed to the Stage.
The environmental information received by the task will be checked against any `environment.yaml` file that exists in the folder corresponding to the task.
If the specific combination is not encountered, the task will create a new folder, take new measurements and produce new output files.
If the configuration of the environment matches the state in an existing `environment.yaml` file, the data in the folder containing it will be used and no
further actions are performed.

In the example case of an `adc` calibration, when the state in the `environment.yaml` of `Target/Calibration/adc/2` matches the state passed to the task,
the `configuration_overlay.yaml` of the directory in `Target/Calibration/adc/2` will be returned as the output of the stage to the following one.
If there is no subsequent stage, the execution terminates.

### Keeping track of quickly changing state:
When performing the scan, the configuration parameters are changed from one 'atomic' measurement to the next. To be able to reconstruct the state of
the Target during any of these 'atomic' measurements all parameters of the target that are changed from measurement to measurement are saved as a
`parameters_*.yaml`. This parameters file will be linked to the corresponding data file via matching filenames. For example, the
`parameters_tws_01.yaml` would store the parameters for the `tws_01.root` file.

Using this approach, a multi dimensional scan would only create data in one directory. It would rely on the analysis software to properly associate
and sort the information of the scan to produce the output of said analysis. The measurement tasks MUST NOT impose a directory structure in their
respective output directory, as this would duplicate structure that is contained in the `.yaml` files.

## State of the Measurement System
Things like the firmware/software version and the default configuration of the diffrerent system components that where used to perform the measurement
are assumed to be Identical for all Procedures in the `Target` folder. These parameters are stored in the `Defaults` directory. There is one file per
system component. So for example the hexacontroller settings, and the ROC default configuration used for all subsequent actions is stored in this
directory. The following is an example with a LD hexaboard as target.
```
HEXB-LD-539345
├── Defaults
│   ├── daq-server.yaml
│   ├── daq-client.yaml
│   ├── slow-control-server.yaml
│   └── ld_hexaboard.yaml
├── Calibration
│   ├── adc
│   │   ├── 1
│   │   └── 2
│   ├── pedestal
│   └── toa-acg
├── Measurements
└── Analyses
```

As can be seen each of the different system components has a default configuration that is stored as part of the `Target` directory and is used as
default for all measurements within that target directory. If the user wants to run measurements with a different default configuration then they must
create a new target directory.
