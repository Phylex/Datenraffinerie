import luigi
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
        if self.analysis_module_path is not None:
            pathstr = str(Path(self.analysis_module_path).resolve())
            sys.path.append(pathstr)
            import distilleries
        else:
            import datenraffinerie_distilleries as distilleries
        distillery = getattr(distilleries, self.name)
        output_paths = distillery.output(self.output_dir)
        return [luigi.LocalTarget(path) for path in output_paths]

    def run(self):
        """ perform the analysis using the imported distillery
        :returns: TODO

        """
        if self.analysis_module_path is not None:
            pathstr = str(Path(self.analysis_module_path).resolve())
            sys.path.append(pathstr)
            import distilleries
        else:
            import datenraffinerie_distilleries as distilleries
        distillery = getattr(distilleries, self.name)
        analysis_data = pd.read_hdf(self.input().path)
        distillery.run(analysis_data, self.output_dir)
