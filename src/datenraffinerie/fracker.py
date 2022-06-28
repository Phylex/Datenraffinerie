from schema import Schema, Or
from os import path
from . import errors
from multiprocessing import Queue, Process
from .analysis_utilities import daq_columns, data_columns, event_mode_data_columns


class Frackers():
    modes = ['full', 'summary']
    fracker_command_schema = Schema({
            'command': Or('reformat', 'stop'),
            'data': Or(path.exists, None),
            'config': Or(path.exists, None)
        })

    def __init__(self, count, default_config_path, columns, mode):
        if not path.exists(default_config_path):
            raise errors.DAQError(f'{default_config_path} does not exist')
        if mode not in self.modes:
            raise errors.DAQError(f'{mode} not in {self.modes}')
        if mode == 'full':
            f_data_columns = event_mode_data_columns
        else:
            f_data_columns = data_columns
        for column in columns:
            if column not in f_data_columns or column not in 
        fracker_processes = []
        task_queue = Queue()
        for i in range(count):
            p = Process(
                    target=self.frack,
                    args=(task_queue, default_config_path, columns))
            fracker_processes.append(p)

    def frack(task_queue, default_config_path, columns):
        
