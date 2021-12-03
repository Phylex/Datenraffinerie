import luigi
from luigi.parameter import ParameterVisibility
from time import sleep
from pathlib import Path

class scan(luigi.Task):
    parameters = luigi.ListParameter(significant=True)
    base_path = luigi.Parameter()
    level = luigi.IntParameter(significant=True, default=0)

    def requires(self):
        tasks = []
        print(self.parameters)
        if len(self.parameters) > 1:
            print("add a level of recursion")
            for path_suffix in self.parameters[0]:
                tasks.append(scan(self.parameters[1:],
                                  self.base_path+path_suffix,
                                  self.level+1))
        else:
            print("lowest level, add the actual tasks")
            for path in self.parameters[0]:
                tasks.append(task_with_file_out(self.base_path+path))
        return tasks

    def run(self):
        with self.output().open('w') as output:
            scan_inputs = [subscan.open('r') for subscan in self.input()]
            for scan_in in scan_inputs:
                output.write(scan_in.read())
                scan_in.close()

    def output(self):
        return luigi.LocalTarget(f'output_level{self.level}')


class task_with_file_out(luigi.Task):
    path = luigi.Parameter(significant=True)

    def run(self):
        p = Path(self.path)
        sleep(3)
        with self.output().open('w') as f:
            f.write("test")

    def output(self):
        return luigi.LocalTarget(self.path)

if __name__ == "__main__":
    run_result = luigi.build([scan([[f'a={i}_' for i in range(3)], [f'b={i}_' for i in range(3)], [f'c={i}' for i in range(3)]], './')], local_scheduler=True)
    print(run_result)
