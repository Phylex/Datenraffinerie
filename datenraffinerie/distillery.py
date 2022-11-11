import luigi
import importlib
import os
import sys
import yaml
from copy import deepcopy
from pathlib import Path
from .analysis_utilities import read_dataframe_chunked
from .analysis_utilities import read_whole_dataframe
from .config_utilities import unfreeze, update_dict
from .errors import OutputError


class Distillery(luigi.Task):
    """ Task that encapsulates analysis tasks and makes them executable
    inside the Datenraffinerie
    """
    system_state = luigi.DictParameter(significant=True)
    priority = luigi.OptionalParameter(significant=False, default=0)

    def requires(self):
        from .valve_yard import ValveYard
        """ Determin which analysis needs to be run to produce
        the data for the analysis
        :returns: The acquisition procedure needed to produce the data
        """
        subtask_state = deepcopy(self.system_state)
        subtask_state['output_path'] = os.path.dirname(
                self.system_state['output_path'])
        subtask_state['name'] = self.system_state['procedure']['daq']
        del subtask_state['procedure']
        return ValveYard(subtask_state)

    def output(self):
        """ Define the files that are produced by the analysis
        :returns: dictionary with the keys 'summary', 'calibration'
            and 'plots', where 'summary's value is a string for a
            relative path to the summary, same as calibration is a
            relative path to the calibration yaml file
            and the value associated to 'plots' is a list of relative
            paths. All paths should be strings.
        """
        analysis_module_path = self.system_state['analysis_module_path']
        output_path = self.system_state['output_path']
        python_module = self.system_state['procedure']['python_module_name']
        parameters = self.system_state['procedure']['parameters']
        analysis = self.import_analysis(analysis_module_path,
                                        python_module)
        analysis_parameters = unfreeze(parameters)
        analysis = analysis(analysis_parameters)
        output = {}
        output['full-calibration'] = self.input()['full-calibration']
        for key, paths in analysis.output().items():
            if paths is None:
                continue
            try:
                if len(paths) == 0:
                    continue
            except TypeError:
                pass
            if key == 'plots':
                try:
                    if len(paths) == 0:
                        continue
                    output['plots'] = [luigi.LocalTarget((Path(output_path)
                                                          / path).resolve())
                                       for path in paths]
                except TypeError as err:
                    raise OutputError('The plots output must be a list ' +
                                      'of paths. Use an empty list if ' +
                                      'no plots are generated') from err
            elif key == 'calibration':
                output['full-calibration']\
                        = (Path(output_path) / paths).resolve()
            else:
                if isinstance(paths, list):
                    output[key] = [Path(output_path) / path for path in paths]
                else:
                    output[key] = Path(output_path) / paths
        return output

    def run(self):
        """ perform the analysis using the imported distillery
        :returns: TODO

        """
        analysis_module_path = self.system_state['analysis_module_path']
        output_path = self.system_state['output_path']
        python_module = self.system_state['procedure']['python_module_name']
        parameters = self.system_state['procedure']['parameters']
        analysis = self.import_analysis(analysis_module_path,
                                        python_module)
        analysis_parameters = unfreeze(parameters)

        # import the class definition
        analysis = self.import_analysis(analysis_module_path,
                                        python_module)
        # instantiate an analysis object from the imported analysis class
        analysis = analysis(analysis_parameters)

        event_mode = self.system_state['event_mode']
        # open and read the data
        if not event_mode:
            analysis.run(read_whole_dataframe(self.input()['data'].path),
                         output_path)
        else:
            in_files = []
            for dfile in self.input()['data']:
                if isinstance(dfile, list):
                    in_files += dfile
                else:
                    in_files.append(dfile)
            data_iter = read_dataframe_chunked([i.path for i in in_files])
            analysis.run(data_iter, output_path)

        # merge the calibrations
        if self.output()['full-calibration'].path\
                != self.input()['full-calibration'].path:
            with self.input()['full-calibration'].open('r') as prev_calib_file:
                previous_calib = yaml.safe_load(prev_calib_file.read())
            with self.output()['full-calibration'].open('w') as new_calib_file:
                new_calib = yaml.safe_load(new_calib_file.read())
                update_dict(previous_calib, new_calib, in_place=True)
                new_calib_file.truncate(0)
                new_calib_file.write(yaml.safe_dump(previous_calib))

    @staticmethod
    def import_analysis(distillery_path: str, name: str):
        """ Import the distillery for the analysis.

        :distillery_path: The path in which to find the distilleries
            module
        :name: The name of the distillery to load
        :returns: the distillery loaded into the local namespace
        """
        if distillery_path is not None:
            pathstr = str(Path(distillery_path).resolve())
            pythonpath_entry = os.path.split(pathstr)[0]
            module_name = os.path.split(pathstr)[1]
            sys.path.append(pythonpath_entry)
            i = importlib.import_module(module_name)
            distillery = getattr(i, name)
        else:
            import datenraffinerie_distilleries as distilleries
            distillery = getattr(distilleries, name)
        return distillery
