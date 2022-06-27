from multiprocessing import Lock, Process
import luigi
from pid import PidFile
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
    lock = Lock()

    def requires(self):
        return pseudo_configuration(self.path, self.identifier)

    def run(self):
        self.lock.acquire()
        sleep(1)
        with self.output()[0].open('w') as f:
            f.write("example data")
        self.lock.release()

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


class test_mp_task(luigi.Task):
    id = luigi.IntParameter(significant=False, default=42)

    def requires(self):
        return None

    @staticmethod
    def parallel_part(target):
        seconds = list(range(target))
        seconds.reverse()
        for i in seconds:
            print(i)
            sleep(1)
        return

    def run(self):
        workers = []
        for i in range(self.id):
            p = Process(target=self.parallel_part, args=(i+1,))
            workers.append(p)
            p.start()
        for w in workers:
            w.join()
        print("run all workers")
        with self.output().open('w') as outf:
            outf.write('done')

    def output(self):
        return luigi.LocalTarget('./out.test')


if __name__ == "__main__":
    run_result = luigi.build([test_mp_task(5)], local_scheduler=True, workers=1)
    # run_result = luigi.build([scan([[f'a={i}_' for i in range(3)], [f'b={i}_' for i in range(3)], [f'c={i}' for i in range(3)]], './', 1)],
    #                          local_scheduler=True,
    #                          workers=5)
    print(run_result)
