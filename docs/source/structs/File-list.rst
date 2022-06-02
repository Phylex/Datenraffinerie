File-List
=========
The file list is the structure that the different tasks return to their respective callers. The file list contains essentially two fields

full-calibration
  This field is the path to the latest calibration file. It is needed so that multiple calibrations can be applied in sequence
  and they accumulate instead of replacing each other

data
  This field contains the data returned from the current task to it's caller. This may be a single item or a List of items
