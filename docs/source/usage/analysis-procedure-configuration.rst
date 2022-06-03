======================
Analysis configuration
======================
Similar to the DAQ procedure, every analysis procedure has it's configuration section that condenses all necessary configuration into the same location
The analysis procedure contains the following fileds

**name** (required)
  The name of the procedure. Must be unique throughout the entire configuration (including daq procedures).

**type** (required)
  specifies the type of the procedure. Possible values are ``daq`` and ``analysis``. For configuring an analysis, ``analysis`` needs to be specified

**daq** (required)
  specifies which daq procedures need to be run in order for this analysis to have the required data. The parameter given must match the ``name`` field
  of a daq procedure. If multiple daq procedures are needed they can be specified using a list, so for example

  ::

    - name: example_analysis
      type: analysis
      daq:
        - example_daq
        - extra_daq

  would require the daq procedures ``example_daq`` and ``extra_daq`` to be defined in the configuration of the Datenraffinerie and be executed before the
  analysis is performed. The Datenraffinerie will automatically execute the specified procedures if not allready done so.

**compatible_modes** (optional)
  Lists which modes the analysis is compatible with. The possible modes are ``summary`` and ``full`` see :doc:`writing analyses </usage/writing-analyses>` for details.
  If the option is not specified it defaults to ``summary`` only.

**provides_calibration** (optional)
  specifies if the analysis performed specifies a calibration file that can be used to update the initial configuration of :doc:`daq procedure </usage/daq-procedure-configuration>`.
  If not specified it is assumed it does not provide a calibration output

**module_name** (optional)
  the module name specifies the python module/class to use for the analysis. This is included so that the same analysis class may be used in different Analysis
  procedures and to avoid using the procedure name to match agains available analyses. If this field is ommitted the name of the procedure is used to search for
  a fitting analysis module

**parameters** (optional)
  This section can be used to pass parameters to the analysis module run by the Datenraffinerie. The structure of this section only depends on what the 
  3rd party analysis expects, as long as the section is valid YAML. the result is passed as dictionary to the analysis's ``__init__()`` function. If
  this field is ommitted None is passed to the init method of the analysis.
