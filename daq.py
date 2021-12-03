import luigi

class DAQ(luigi.WrapperTask):
    daq_server_config = luigi.Parameter()
    daq_client_config = luigi.Parameter()
    target_config = luigi.Parameter()

    def requires(self):
        :
