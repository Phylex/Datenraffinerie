===========================
DAQ procedure configuration
===========================
A DAQ procedure is one type of procedure of the Datenraffinerie. It's primary job is to aquire data from the device under test (DUT).
To be able to collect the Data from the DUT the Datenraffinerie needs to be propely configured. A daq procedure configuration is an enty
in a YAML list. Every entry is a fully contained procedure configuration and does not directly depend on any other procedure being defined.

The daq procedure configuration includes the configuration for the daq system and DUT to collect all neccessary configuration into a single place
for good visibility into the configuration of the target and DAQ system.

------
Fields
------
The daq procedure configuration consists of the following Fields. Each field controls a specific aspect of the behaviour of the Datenraffinerie
or defiens the configuration of the DUT and DAQ system directly.

**name**
  Each procedure has a name. The name must be unique, meaning there must be no two procedure configurations with the same name.

**type**
  Each procedure needs a type. There are currently two types of procedures, ``daq`` and ``analysis``

**merge**
  Specifies if the Datenraffinerie should merge the data resulting from the DAQ procedure into one file or if the files should not be merged to aviod
  losing performance when loading/searching for data in the file. If the result of the merge is too large it may not be able to fit into main memmory.

**mode**
  Specifies the mode of operation of the Datenraffinerie. Current modes are ``summary`` and ``full``.

**system_settings**
  The system_settings field has multiple subfields. All these fields relate to the configuration of the DUT/DAQ system. See `System settings`_ for more details

**parameters**
  The parameters section is a list of either template/value pairs or key/value pairs. Each entry specifies a *dimension* of the scan to be performed. The final scan
  will be a cartesian product of all dimensions. See `Parameters`_ for more details.

-----

.. _`System settings`:

---------------
System settings
---------------
The Target settings specify the configuration of the DUT/target device and DAQ system.

**default**
  this specifies the *relative path* to the yaml file containing the default configuration of the DUT. This configuration should list every parameter of the
  DUT and the value of the parameter after power-up or reset. It is assumed that the device is in this state after a reset command is sent to the DAQ system.
  The default is used internally to help improve performance of the program and ensure that no unneccessary configuration command is sent to the device.
  Multiple files may be specified as a list and act as if they where appended into a single file. Every file needs to be valid YAML.
  If values are specified in more than one file the value from the the last file that the value occurs in is used. Later values overwrite earlier ones

**init**
  This field specifies the *relative path* to the yaml file containing the initial parameters of the DUT needed to perform the procedure this config describes
  This file only needs to list the parameters that are different from the default. The initial configuration is used as the basis for applying the config modifications
  specified by the `parameters`_ to.
  Multiple files may be specified as a list and act as if they where appended into a single file. Every file needs to be valid YAML.
  If values are specified in more than one file the value from the the last file that the value occurs in is used. Later values overwrite earlier ones

**override**
  This field offers the possibility to further modify or extend the configuration specified in the file listed in the *init* field. The intent behind this is that
  when two daq procedures differ only slightly, it is possible to specify a common init file and then list the differences as *override* parameters. The override parameters
  only apply to the init and do not affect the default values of the parameters. 

-----

.. _`Parameters`:

----------
Parameters
----------
The parameters are at the heart of the Datenraffinerie. The definition of the parameters from this section is used to generate the set of measurements to be performed during
the procedure.

The parameters section is a list of key/range and/or template/range paris. Every entry of this list describes one dimension of the procedure. The total amount of measurements will be 
the cartesian product of all measurements from the different dimensions.

::

  - key: [this]
    range:
      start: 0
      stop: 4
      step: 1
  - key: [that]
    range:
      start: 0
      stop: 3
      step: 1

would result in the following set of patches being generated:

::

  - {this: 0, that: 0}
  - {this: 0, that: 1}
  - {this: 0, that: 2}
  - {this: 1, that: 0}
  - {this: 1, that: 1}
  - {this: 1, that: 2}
  - {this: 2, that: 0}
  - {this: 2, that: 1}
  - {this: 2, that: 2}
  - {this: 3, that: 0}
  - {this: 3, that: 1}
  - {this: 3, that: 2}

There are two ways of specifying the values that are to be assumed for the dimension specified.

**range**
  This specifies a regularly spaced set of values to assume for the key specified for this dimension.
  ``range`` has three fields. The optional ``start`` set the start value of the dimension, ``stop`` sets the stop value
  and the optional ``step`` value sets the step between the values assumed in the range. If step is omitted
  it is assumed to be 1. If ``start`` is ommitted, it is assumed to be 0.

**values**
  This specifies a list of individual values. The values are allowed to be dictionaries/configuration fragments to allow for the iteration
  over a complex sequence of configurations that may change different values for each step. It is assumed that the value, even if it is a complex
  structure is the value for the specified key. The key may be ommitted when using specifying individual values. If ommitted, the values need to be 
  valid configuration fragments.

Key generation
==============
Similar to the value, the key can also be specified in two different ways.

**template**
  when specify a template for the key, the jinja templating engine together with the possibility of specifying raw strings in yaml is used to encapsulate
  a yaml string as template and then fill in the value in the template before parsing the result as yaml. The location of the value in the template is specified
  via the ``{{ value }}`` string inside the template string. The following example should provide some insight into how the templating works:

  ::

    - template: |-
       roc_s0:
         ch:
           {{ value }}:
             Channeloff: 1
      range:
        stop: 3

  results in the following set of patches:

  ::

    - {roc_s0: {ch: {0: Channeloff: 1}}}
    - {roc_s0: {ch: {1: Channeloff: 1}}}
    - {roc_s0: {ch: {2: Channeloff: 1}}}


**key**
  The key is specified as a list. The list may contain sublists which may recursively contain sublists. Each element of the list is taken to be a (sub)key of equal depth
  to the position of the list. Again an example explains this best:
  
  ::

    - key: [this, [that, other], stuff, [foo, bar]]
      values:
      - 0

  results in:
  ::
    
    this:
      that:
        stuff:
          foo: 0 
          bar: 0 
      other:
        stuff:
          foo: 0 
          bar: 0

