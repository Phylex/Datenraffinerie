from setuptools import setup

setup(
    entry_points={
        'console_scripts': [
            'datenraffinerie = datenraffinerie.datenraffinerie:cli',
            'generate-configs = datenraffinerie.gen_configurations:generate_configuratons',
            'acquire-data = datenraffinerie.acquire_data:acquire_data',
            'coordinate-daq-access = datenraffinerie.daq_coordination:main',
            'process-raw-data = datenraffinerie.frack_data:main'
        ]
    },
    install_requires=[
        'Click',
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
        'bson',
    ]
)
