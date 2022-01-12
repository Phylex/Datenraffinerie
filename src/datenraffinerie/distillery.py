import luigi
import importlib
import os
import sys
from pathlib import Path
import pandas as pd


class DistilleryAdapter(luigi.Task):
    """ Task that encapsulates analysis tasks and makes them executable
    inside the Datenraffinerie
    """
    name = luigi.Parameter(significant=True)
    daq = luigi.Parameter(significant=True)
    output_dir = luigi.Parameter(significant=True)
    parameters = luigi.DictParameter(significant=True)
    root_config_path = luigi.Parameter(significant=True)
    analysis_module_path = luigi.OptionalParameter(significant=True,
                                                   default=None)

    def requires(self):
        from .valve_yard import ValveYard
        """ Determin which analysis needs to be run to produce
        the data for the analysis
        :returns: The acquisition procedure needed to produce the data
        """
        return ValveYard(self.root_config_path, self.daq, self.output_dir,
                         self.analysis_module_path)

    def output(self):
        """ Define the files that are produced by the analysis
        :returns: list of strings 
        """
        distillery = self.import_distillery(self.analysis_module_path,
                                            self.name)
        distillery = distillery(self.parameters)
        output_paths = distillery.output()
        return [luigi.LocalTarget(Path(path).resolve())
                for path in output_paths]

    def run(self):
        """ perform the analysis using the imported distillery
        :returns: TODO

        """
        # import the class definition
        distillery = self.import_distillery(self.analysis_module_path,
                                            self.name)
        # instantiate an analysis object from the imported analysis class
        distillery = distillery(self.parameters)

        # open and read the data
        data = pd.read_hdf(self.input().path)
        distillery.run(data, self.output_dir)

    @staticmethod
    def import_distillery(distillery_path: str, name: str):
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
