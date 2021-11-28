# Datenraffinerie

A set of luigi tasks to handle the processing of the characterisation of HGCAL test system data

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
execution called `environment.yaml`

### Taking new data if the environment is different
When a Stage is executed, environmental information in form of a `*.yaml` file may be passed to the Stage.
The environmental information received by the task will be checked against any `environment.yaml` file that exists in the folder corresponding to the task.
If the specific combination is not encountered, the task will create a new folder, take new measurements and produce new output files.
If the configuration of the environment matches the state in an existing `environment.yaml` file, the data in the folder containing it will be used and no
further actions are performed.

In the example case of an `adc` calibration, when the state in the `environment.yaml` of `Target/Calibration/adc/2` matches the state passed to the task,
the `configuration_overlay.yaml` of the directory in `Target/Calibration/adc/2` will be returned as the output of the stage to the following one.
If there is no subsequent stage, the execution terminates.
