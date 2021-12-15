import luigi
from valve_yard import ValveYard

if __name__ == '__main__':
    RUN_RESULT = luigi.build([ValveYard(
        './test_configurations/main_config.yaml',
        'timewalk_scan', './test_out')])
