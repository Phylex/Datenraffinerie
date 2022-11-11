from setuptools import setup

setup(
    entry_points={
        'console_scripts': [
            'datenraffinerie = datenraffinerie.datenraffinerie:cli',
            'generate-configs = datenraffinerie.gen_configurations:generate_configuratons',
            'acquire-data-single-threaded = datenraffinerie.acquire_data:acquire_data',
            'acquire-data = datenraffinerie.acquire_data:pipelined_main',
            'coordinate-daq-access = datenraffinerie.daq_coordination:main',
            'process-raw-data-single-threaded = datenraffinerie.frack_data:main',
            'process-raw-data = datenraffinerie.postprocessing_queue:main',
            'yaml-utils = datenraffinerie.yaml_utils:cli',
            'show-hdf = datenraffinerie.print_h5:show_hdf',
            'read-rocs = datenraffinerie.read_rocs:cli',
            'full-daq = datenraffinerie.full_daq:main',
        ]
    },
    install_requires=[
        'luigi',
        'pandas',
        'matplotlib',
        'numpy',
        'scipy',
        'uproot',
        'pyyaml',
        'zmq',
        'pytest',
        'awkward',
        'tables',
        'h5py',
        'numba',
        'jinja2',
        'schema',
        'hgcroc-configuration-client',
        'progress',
        'pymongo',
        'rich',
    ]
)
