import logging
import luigi
from valve_yard import ValveYard

logger = logging.getLogger('hexactrl_script')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('new_daq_timewalk_scan.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s : %(name)s  -  %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

if __name__ == '__main__':
    RUN_RESULT = luigi.build([ValveYard(
        './test_configurations/main_config.yaml',
        'timewalk_scan', './test_out')],
        local_scheduler=True,
        workers=1)
