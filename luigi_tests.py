import luigi
from luigi.parameter import ParameterVisibility
from time import sleep
from pathlib import Path
import operator
from functools import reduce

class scan(luigi.Task):
    parameters = luigi.ListParameter(significant=True)
    base_path = luigi.Parameter()
    identifier = luigi.IntParameter(significant=True, default=0)

    def requires(self):
        tasks = []
        print(self.parameters)
        if len(self.parameters) > 1:
            task_id_offset = reduce(operator.mul,
                                    [len(param) for param in
                                     self.parameters[1:]])
            print("add a level of recursion")
            for i, path_suffix in enumerate(self.parameters[0]):
                tasks.append(scan(self.parameters[1:],
                                  self.base_path+path_suffix,
                                  self.identifier + 1 + (task_id_offset * i)))
        else:
            print("lowest level, add the actual tasks")
            for i, path in enumerate(self.parameters[0]):
                tasks.append(Format(self.base_path+path,
                                    self.identifier + i))
        return tasks

    def run(self):
        with self.output().open('w') as output:
            scan_inputs = [subscan.open('r') for subscan in self.input()]
            for scan_in in scan_inputs:
                output.write(scan_in.read())
                scan_in.close()

    def output(self):
        return luigi.LocalTarget(f'output_level{self.identifier}')

class Format(luigi.Task):
    path = luigi.Parameter(significant=True)
    identifier = luigi.Parameter(significant=True)

    def requires(self):
        return pseudo_measurement(self.path, self.identifier)

    def output(self):
        return luigi.LocalTarget(self.path + '_' + str(self.identifier) + '.hdf5')

    def run(self):
        with self.output().open('w') as format_out:
            for measurement_out in self.input():
                with measurement_out.open('r') as inp:
                    format_out.write(inp.read())

class pseudo_measurement(luigi.Task):
    path = luigi.Parameter(significant=True)
    identifier = luigi.Parameter(significant=True)

    def requires(self):
        return pseudo_configuration(self.path, self.identifier)

    def run(self):
        with self.output()[0].open('w') as f:
            f.write("example data")

    def output(self):
        return (luigi.LocalTarget(self.path+'_'+str(self.identifier)+'-data'), self.input())


class pseudo_configuration(luigi.Task):
    path = luigi.Parameter(significant=True)
    identifier = luigi.Parameter(significant=True)

    def run(self):
        with self.output().open('w') as config_file:
            config_file.write('example config')

    def output(self):
        return luigi.LocalTarget(self.path+'_'+str(self.identifier)+'-config')


if __name__ == "__main__":
    run_result = luigi.build([scan([[f'a={i}_' for i in range(3)], [f'b={i}_' for i in range(3)], [f'c={i}' for i in range(3)]], './', 1)], local_scheduler=True)
    print(run_result)
