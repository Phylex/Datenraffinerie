import zmq
import sys
import bson
import yaml
import logging
import click
import shutil
import subprocess as sp
from pathlib import Path
from .control_adapter import DAQSystem
from hgcroc_configuration_client.client import Client as SCClient
from schema import Schema, Or
from schema import SchemaError
from .errors import DAQError
import uuid
from time import sleep
from time import ctime
import os


class DAQCoordCommand():
    valid_commands = ['acquire lock', 'shutdown', 'release lock',
                      'reset_target', 'read_target', 'initialize',
                      'measure', 'configure']
    schema = Schema(Or({
        'command': Or('acquire lock', 'shutdown'),
        'locking_token': None,
        'config': None
    }, {
        'command': 'release lock',
        'locking_token': str,
        'config': None
    }, {
        'command': 'reset_target',
        'locking_token': str,
        'config': None,
    }, {
        'command': 'read_target',
        'locking_token': str,
        'config': Or(str, None)
    }, {
        'command': 'initialize',
        'locking_token': str,
        'config': str
    }, {
        'command': 'measure',
        'locking_token': str,
        'config': str,
        'readback': bool
    }, {
        'command': 'configure',
        'locking_token': str,
        'config': str,
        'readback': bool
    }))

    def __init__(self, command: str, locking_token=None,
                 config=None, readback: bool = False):
        self.command = command if command in self.valid_commands else None
        if command in self.valid_commands[2:] and locking_token is None:
            raise DAQError(f"For a message with the command: {command}, a "
                           "locking token is required")
        self.locking_token = locking_token
        if command in self.valid_commands[5:] and config is None:
            raise DAQError("For a message of type 'initialize', 'configure"
                           "or 'measure' a configuration dict is required")
        if not isinstance(readback, bool):
            raise DAQError('The measurement Command needs a readback '
                           'argument that is a bool')
        self.readback = readback
        self.config = config

    def serialize(self):
        config = None
        if self.config is not None:
            config = yaml.dump(self.config)
        msg_dict = {'command': self.command,
                    'locking_token': self.locking_token,
                    'config': config}
        if self.command in self.valid_commands[6:]:
            msg_dict['readback'] = self.readback
        return bson.encode(msg_dict)

    @staticmethod
    def parse(message: bytes):
        try:
            message_dict = bson.decode(message)
        except:
            raise DAQError('Unable to decode bson message')
        try:
            valid_message = DAQCoordCommand.schema.validate(message_dict)
        except SchemaError as err:
            raise ValueError(
                'Message validation failed for message: '
                f'{message_dict}\n Got Error: {err}')
        parsed_config = None
        if message_dict['config'] is not None:
            parsed_config = yaml.safe_load(valid_message['config'])
        try:
            readback = valid_message['readback']
        except KeyError:
            readback = False
        return DAQCoordCommand(command=valid_message['command'],
                               locking_token=valid_message['locking_token'],
                               config=parsed_config,
                               readback=readback)


class DAQCoordResponse():
    valid_responses = ['error', 'data', 'lock', 'ack', 'access denied',
                       'target_config']
    schema = Schema(Or({
        'type': 'error',
        'content': str
    }, {
        'type': 'data',
        'content': bytes
    }, {
        'type': 'lock',
        'content': Or(str, None)
    }, {
        'type': Or('ack', 'access denied'),
        'content': None
    }, {
        'type': 'target_config',
        'content': str
    })
    )

    def __init__(self, type: str, content=None):
        if type not in self.valid_responses:
            raise DAQError('daq response not valid')
        self.type = type
        if type == 'target_config' and not isinstance(content, dict):
            raise DAQError('The target config needs to be a dict')
        self.content = content
        if type == 'data' and not isinstance(content, bytes):
            raise DAQError('The data needs to be of type bytes')

    def serialize(self, logger):
        if self.type == 'error':
            if self.content is None:
                raise DAQError('daq error response was attempted but'
                               'no error was given')
            else:
                return bson.encode(
                    {'type': 'error', 'content': self.content})
        if self.type == 'data':
            if self.content is None:
                raise DAQError('No data provided to the daq response')
            else:
                logger.debug(f'binary Data is {len(self.content)} bytes long')
                return bson.encode(
                    {'type': 'data',
                     'content': bson.Binary(self.content, subtype=0)})
        if self.type == 'lock':
            return bson.encode(
                {'type': 'lock', 'content': str(self.content)})
        if self.type == 'ack':
            return bson.encode({'type': 'ack', 'content': None})
        if self.type == 'target_config':
            return bson.encode({'type': 'target_config',
                                'content': yaml.safe_dump(self.content)})

    @staticmethod
    def parse(message: bytes, logger):
        rsp_dict = bson.decode(message)
        if rsp_dict['type'] == 'data':
            logger.debug(f'Received {len(rsp_dict["content"])} bytes of data')
        valid_message = DAQCoordResponse.schema.validate(rsp_dict)
        if valid_message['type'] == 'target_config':
            valid_message['content'] = yaml.safe_load(valid_message['content'])
        return DAQCoordResponse(type=valid_message['type'],
                                content=valid_message['content'])

    def __str__(self):
        return f'{self.type}: {self.content}'


class DAQCoordClient():
    def __init__(self, network_config: dict):
        self.logger = logging.getLogger('daq_coord_client')
        self.lock = None
        self.zmq_transaction_running = False
        self.raw_response = None
        self.io_context = zmq.Context()
        self.socket = self.io_context.socket(zmq.REQ)
        socket_address = \
            f"tcp://{network_config['daq_coordinator']['hostname']}:" +\
            f"{network_config['daq_coordinator']['port']}"
        self.socket.connect(socket_address)
        self.logger.info('Initializing')
        response = DAQCoordResponse(type='lock', content=None)
        try_count = 20
        while response.content is None and try_count > 0:
            if try_count != 20:
                sleep(10)
            self.logger.debug('attempting to aquire lock')
            message = DAQCoordCommand(command='acquire lock')
            self.socket.send(message.serialize())
            response = DAQCoordResponse.parse(self.socket.recv(), self.logger)
            self.logger.debug(f'Received response: {response}')
            try_count -= 1
        if response.content is not None:
            self.logger.info('Acquired lock')
            self.lock = response.content
        else:
            raise ValueError('Lock could not be acquires within the timeout '
                             'period')

    def initialize(self, config: dict, start_tdcs: bool = False):
        message = DAQCoordCommand(command='initialize',
                                  locking_token=self.lock,
                                  config=config)
        self.logger.info('Sending initial config')
        self.logger.debug(f'\n{config}')
        self.socket.send(message.serialize())
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        response = DAQCoordResponse.parse(self.raw_response, self.logger)
        self.logger.debug(f'Received response:\n{response}')
        if response.type == 'error':
            self.logger.error(
                f"Received error from coordinator: {response.content}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')
        self.logger.info('initialized')
        if start_tdcs:
            rocs = list(filter(
                lambda x: 'roc_s' in x, config['target'].keys()))
            self._start_tdcs(rocs)

    def measure(self, run_config: dict, readback=False):
        message = DAQCoordCommand(command='measure', locking_token=self.lock,
                                  config=run_config, readback=readback)
        raw_msg = message.serialize()
        self.socket.send(raw_msg)
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        response = DAQCoordResponse.parse(self.raw_response, self.logger)
        if response.type == 'error':
            self.logger.error(
                f"Received error from coordinator: {response.content}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')
        return response.content

    def read_target(self, config: dict = None):
        message = DAQCoordCommand(
            command='read_target',
            locking_token=self.lock,
            config=config
        )
        raw_msg = message.serialize()
        self.socket.send(raw_msg)
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        response = DAQCoordResponse.parse(self.raw_response, self.logger)
        if response.type == 'error':
            self.logger.error(
                f"Received error from coordinator: {response.content}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')
        return response.content

    def __del__(self):
        if self.zmq_transaction_running:
            response = self.socket.recv()
            response = DAQCoordResponse.parse(response, self.logger)
            if response.type != 'error':
                self.logger.info(
                    f"Receive message of type {response.type}"
                    "from coordinator, discarding")
            if response.type == 'error':
                self.logger.error(
                    f"Received error from coordinator: {response.content}")
        if self.lock is not None:
            message = DAQCoordCommand(
                command='release lock', locking_token=self.lock)
            self.socket.send(message.serialize())
            response = DAQCoordResponse.parse(self.socket.recv(), self.logger)
            if response.type == 'error':
                self.logger.error(
                    f"Received error from coordinator: {response.content}")
                raise ValueError(
                    'Server responded with an error state: '
                    f'{response.content}')
        self.socket.close()
        self.io_context.destroy()

    def reset_target(self):
        self.logger.info('Resetting Target')
        message = DAQCoordCommand(
            command='reset_target',
            locking_token=self.lock,
            config=None)
        self.socket.send(message.serialize())
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        response = DAQCoordResponse.parse(self.raw_response, self.logger)
        if response.type == 'error':
            self.logger.error(
                f"Received error from coordinator: {response.content}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')
        elif response.type != 'ack':
            self.logger.error(
                "Received unexpected response from coordinator: "
                f"{response}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')
        self.logger.info('Target successfully reset')
        return

    def _start_tdcs(self, rocs: list, readback=False):
        self.logger.info('Starting up Master TDCs')
        config = {'target': {}}
        for roc in rocs:
            config['target'][roc] = \
                {'MasterTdc':
                    {0: {'EN_MASTER_CTDC_VOUT_INIT': 1,
                         'VD_CTDC_P_DAC_EN': 1,
                         'VD_CTDC_P_D': 16,
                         'EN_MASTER_FTDC_VOUT_INIT': 1,
                         'VD_FTDC_P_DAC_EN': 1,
                         'VD_FTDC_P_D': 16},
                     1: {'EN_MASTER_CTDC_VOUT_INIT': 1,
                         'VD_CTDC_P_DAC_EN': 1,
                         'VD_CTDC_P_D': 16,
                         'EN_MASTER_FTDC_VOUT_INIT': 1,
                         'VD_FTDC_P_DAC_EN': 1,
                         'VD_FTDC_P_D': 16}
                     }
                 }
        message = DAQCoordCommand(command='configure',
                                  config=config,
                                  locking_token=self.lock,
                                  readback=readback)
        self.logger.info('Sending configure command with config: ')
        self.logger.debug(f'\n{config}')
        self.socket.send(message.serialize())
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        response = DAQCoordResponse.parse(self.raw_response, self.logger)
        if response.type == 'error':
            self.logger.error(
                f"Received error from coordinator: {response.content}")
            raise ValueError(
                'Server responded with an error state: '
                f'{response.content}')

        config = {'target': {}}
        for roc in rocs:
            config['target'][roc] = \
                {'MasterTdc':
                    {0: {'EN_MASTER_CTDC_VOUT_INIT': 0,
                         'EN_MASTER_FTDC_VOUT_INIT': 0
                         },
                     1: {'EN_MASTER_CTDC_VOUT_INIT': 0,
                         'EN_MASTER_FTDC_VOUT_INIT': 0
                         }
                     }
                 }
        message = DAQCoordCommand(command='configure',
                                  config=config,
                                  locking_token=self.lock,
                                  readback=readback)
        self.logger.info('Sending configure command with config: ')
        self.logger.debug(f'\n{config}')
        self.socket.send(message.serialize())
        self.zmq_transaction_running = True
        self.raw_response = self.socket.recv()
        self.zmq_transaction_running = False
        self.logger.info('Master TDCs set up')


class DAQCoordinator():

    def __init__(self, network_config, capture_data):
        self.capture_data = capture_data
        self.network_config = network_config
        self.logger = logging.getLogger('daq_coordinator')
        self.lock = None
        self.initialized = False
        self.run_counter = 0
        self.measurement_data_path = Path('/tmp/measurement_data.raw')
        self.logger.info('creating ZMQ context and socket for Coordinator')
        self.io_context = zmq.Context()
        self.command_socket = self.io_context.socket(zmq.REP)
        socket_address = \
            f"tcp://{self.network_config['daq_coordinator']['hostname']}:" +\
            f"{self.network_config['daq_coordinator']['port']}"
        self.command_socket.bind(socket_address)
        self.logger.debug('bound to: %s' % socket_address)
        self.logger.info('Initializing target-adapter')
        self.target = SCClient(
            self.network_config['server']['hostname'],
            self.network_config['server']['sc_ctrl_port'])
        self.logger.info('Initializing DAQ-System adapter')
        self.daq_system = DAQSystem(
            client_hostname=network_config['client']['hostname'],
            client_port=network_config['client']['port'],
            server_hostname=network_config['server']['hostname'],
            server_port=network_config['server']['daq_ctrl_port'],
            data_port=network_config['server']['data_port'])

    def run(self):
        while True:
            message = self.command_socket.recv()
            daq_response = None
            try:
                daq_command = DAQCoordCommand.parse(message)
                command = daq_command.command
                self.logger.info(f'Received a {command} command')
            except DAQError as e:
                self.logger.info('Received invalid command')
                daq_response = DAQCoordResponse(
                    type='error',
                    content=f"Parsing of the daq_command "
                            f"{daq_command.command} failed with "
                            f"the error: {e}")
                self.command_socket.send(daq_response.serialize(self.logger))
                self.lock = None
                continue

            # check for the different kind of messages
            if command == 'acquire lock':
                if self.lock is None:
                    self.lock = str(uuid.uuid1())
                    self.logger.info(
                        f'No lock set, acquiring lock: {self.lock}')
                    daq_response = DAQCoordResponse(type='lock',
                                                    content=self.lock)
                else:
                    self.logger.info(
                        'DAQ-System is locked, sending empty response')
                    daq_response = DAQCoordResponse(type='lock',
                                                    content=None)
                self.command_socket.send(daq_response.serialize(self.logger))
                continue

            # all messages beyond this point need a locking token to work
            # so respond with an error here if no locking token can be found
            msg_lock = daq_command.locking_token
            self.logger.debug(f'Received lock from cliend: {msg_lock}')
            if self.lock != msg_lock:
                self.logger.warn(
                    f'Lock in the message does not match {self.lock}'
                    'responing with access denied')
                daq_response = DAQCoordResponse(type='access denied')
                self.command_socket.send(daq_response.serialize(self.logger))
                continue

            if command == 'release lock':
                daq_response = DAQCoordResponse(
                    type='ack',
                    content=None)
                self.lock = None
                self.logger.info('releasing lock')
                self.command_socket.send(daq_response.serialize(self.logger))
                if self.initialized:
                    self.logger.info('Deinitializing DAQ system')
                    self.daq_system.tear_down_data_taking_context()
                    self.initialized = False
                    self.run_counter = 0
                continue

            if command == 'initialize':
                config = daq_command.config
                self.logger.debug(
                    'Received initialization config:\n' +
                    yaml.dump(config))
                try:
                    self.logger.info('Resetting ROCs')
                    self.target.reset()
                    self.logger.debug(
                        'Initializing DAQ-System and setting up data'
                        'taking context')
                    self.daq_system.initialize(initial_config=config)
                    self.daq_system.setup_data_taking_context()
                except ValueError as err:
                    self.logger.warn(
                        'initialization of the daq system failed, received'
                        f'error: {err.args[0]}')
                    error_msg = 'During initialization of the daq system ' + \
                                f'an error ocurred: {err.args[0]}'
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=error_msg
                    )
                    self.command_socket.send(
                        daq_response.serialize(self.logger))
                    continue
                try:
                    target_config = config['target']
                except KeyError:
                    target_config = {}
                if target_config != {}:
                    self.logger.debug('Initializing target system')
                    try:
                        self.logger.debug(
                            'Initializing Rocs\n'
                            f'{yaml.dump(target_config)}')
                        self.target.set(target_config,
                                        readback=daq_command.readback)
                    except ValueError as err:
                        self.logger.warn(
                            'target configuration failed. Got the error: '
                            f'{err.args[0]} from the sc-server')
                        error_msg = \
                            'During configuration of the ROCs an error ' + \
                            f'ocurred: {err.args[0]}'
                        daq_response = DAQCoordResponse(
                            type='error',
                            content=error_msg
                        )
                        self.command_socket.send(
                            daq_response.serialize(self.logger))
                        continue
                else:
                    self.logger.debug('No target config found, '
                                      'target initialization skipped')
                self.logger.info('DAQ-System and target initialized')
                response = DAQCoordResponse(type='ack')
                self.initialized = True
                self.command_socket.send(response.serialize(self.logger))
                continue

            if command == 'configure':
                self.logger.info('Configuring DAQ-System')
                config = daq_command.config
                self.logger.debug(
                    'Received system config:\n' +
                    yaml.dump(config))
                try:
                    self.daq_system.configure(config)
                except ValueError as err:
                    self.logger.warn(
                        'initialization of the daq system failed, received'
                        f'error: {err.args[0]}')
                    error_msg = 'During initialization of the daq system ' + \
                                f'an error ocurred: {err.args[0]}'
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=error_msg
                    )
                    self.command_socket.send(
                        daq_response.serialize(self.logger))
                    continue
                try:
                    target_config = config['target']
                except KeyError:
                    target_config = {}
                if target_config != {}:
                    self.logger.debug('Configuring target system')
                    try:
                        self.logger.debug(
                            'Configuring Rocs\n'
                            f'{yaml.dump(target_config)}')
                        self.target.set(target_config,
                                        readback=daq_command.readback)
                    except ValueError as err:
                        self.logger.warn(
                            'target configuration failed. Got the error: '
                            f'{err.args[0]} from the sc-server')
                        error_msg = \
                            'During configuration of the ROCs an error ' + \
                            f'ocurred: {err.args[0]}'
                        daq_response = DAQCoordResponse(
                            type='error',
                            content=error_msg
                        )
                        self.command_socket.send(
                            daq_response.serialize(self.logger))
                        continue
                else:
                    self.logger.debug('No target config found, '
                                      'target initialization skipped')
                self.logger.info('DAQ-System and target configured')
                response = DAQCoordResponse(type='ack')
                self.command_socket.send(response.serialize(self.logger))
                continue

            if command == 'measure':
                if not self.initialized:
                    self.logger.error(
                        'DAQ system has not been initialized yet')
                    daq_response = DAQCoordResponse(
                        type='error',
                        content='The daq coordinator must be initialized'
                        ' before measurements can be taken'
                    )
                    self.command_socket.send(
                        daq_response.serialize(self.logger))
                    continue
                config = daq_command.config
                self.logger.debug(
                    'Received run configuration:\n'
                    + yaml.dump(config))
                try:
                    target_config = config['target']
                except KeyError:
                    target_config = {}
                if target_config != {}:
                    self.logger.info('Configuring target system')
                    try:
                        self.target.set(target_config,
                                        readback=daq_command.readback)
                    except ValueError as err:
                        self.logger.warn(
                            'target configuration failed. Got the error: '
                            f'{err.args[0]} from the sc-server')
                        error_msg = \
                            'During configuration of the ROCs an error ' + \
                            f'ocurred an error ocurred: {err.args[0]}'
                        daq_response = DAQCoordResponse(
                            type='error',
                            content=error_msg
                        )
                        self.command_socket.send(
                            daq_response.serialize(self.logger))
                        continue
                else:
                    self.logger.debug('No target config found, '
                                      'target configuration skipped')
                try:
                    self.logger.debug('Configuring daq-system')
                    self.daq_system.configure(config)
                    self.logger.info('Acquiring Data')
                    self.daq_system.take_data(self.measurement_data_path)
                except ValueError as err:
                    self.logger.warn(
                        'Data taking failed. Got the error: '
                        f'{err.args[0]} from the DAQ-system')
                    error_msg = \
                        'During the Data taking the DAQ system encountered' \
                        f' an error: {err.args[0]}'
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=error_msg
                    )
                    self.command_socket.send(
                        daq_response.serialize(self.logger))
                    continue
                except RuntimeWarning as warn:
                    self.logger.warn(
                        'Data taking failed. Got the warning: '
                        f'{warn.args[0]} from the DAQ-system')
                    error_msg = \
                        'The DAQ system encountered' \
                        f' an error: {warn.args[0]}'
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=error_msg
                    )
                    self.command_socket.send(
                        daq_response.serialize(self.logger))
                with open(self.measurement_data_path, 'rb') as data_file:
                    self.logger.info('Sending Acquired data to clinet')
                    daq_response = DAQCoordResponse(
                        type='data',
                        content=data_file.read()
                    )
                if self.capture_data:
                    storage_file_name = \
                        Path(self.lock + f'_run_{self.run_counter}_data.raw')
                    self.logger.info(
                        'Storing Data locally in file: '
                        f'{storage_file_name}')
                    os.rename(self.measurement_data_path,
                              storage_file_name.absolute())
                self.run_counter += 1
                self.command_socket.send(daq_response.serialize(self.logger))
                self.logger.info('Data sent')
                continue

            if command == 'read_target':
                read_config = daq_command.config
                self.logger.info('Received request to read out the target')
                try:
                    config = self.target.get_from_hardware(read_config)
                    self.logger.info(
                        'Read Config from the hardware, sending it to '
                        'the client')
                    daq_response = DAQCoordResponse(
                        type='target_config',
                        content={'target': config}
                    )
                except ValueError as err:
                    self.logger.error(
                        f'Received error from the Target: {err.args[0]}')
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=f'{err.args[0]}'
                    )
                self.command_socket.send(daq_response.serialize(self.logger))
                self.logger.info('target config sent to client')
                continue

            if command == 'reset_target':
                self.logger.info('Received request to reset target')
                try:
                    self.target.reset()
                    self.logger.info('Sending target reset command')
                    daq_response = DAQCoordResponse(
                        type='ack')
                except ValueError as err:
                    self.logger.error(
                        f'Received error from the Target: {err.args[0]}')
                    daq_response = DAQCoordResponse(
                        type='error',
                        content=f'{err.args[0]}'
                    )
                self.command_socket.send(daq_response.serialize(self.logger))
                self.logger.info('Target Reset')
                continue

            if command == 'shutdown':
                daq_response = DAQCoordResponse(
                    type='ack'
                )
                self.command_socket.send(daq_response.serialize())
                self.logger.info('Shutting down')
                break


_log_level_dict = {'DEBUG': logging.DEBUG,
                   'INFO': logging.INFO,
                   'WARNING': logging.WARNING,
                   'ERROR': logging.ERROR,
                   'CRITICAL': logging.CRITICAL}


@click.command()
@click.argument('netcfg', type=click.File('r'),
                metavar='[network configuration file]')
@click.option('--log/--no-log', type=bool, default=True,
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
@click.option('--client_output', default=None,
              help='file to place the output of the client into, by default'
                   ' the output of the daq-client is not captured')
@click.option('--capture_data/--dont_capture_data', default=False)
def main(netcfg, log, loglevel, client_output, capture_data):
    if client_output is not None:
        client_output = Path(client_output)
    if log:
        logging.basicConfig(filename='daq-coord.log',
                            filemode='a+',
                            level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)-10s:'
                                   '%(name)-50s %(message)s')
    logging.info('Read in network config')
    try:
        netcfg = yaml.safe_load(netcfg.read())
        netcfg['client'] = {}
        netcfg['client']['hostname'] = 'localhost'
        netcfg['client']['port'] = 6001
    except yaml.YAMLError as err:
        sys.exit('Error reading in the network config:\n' +
                 + str(err) + '\nexiting ..')

    logging.info('Starting daq-client')
    daq_client_path = shutil.which('daq-client')
    if daq_client_path is None:
        logging.error('daq-client executable not found, exiting')
        print('daq-client executable not found, exiting')
        sys.exit(1)
    if client_output is None:
        logging.info('discarding client output')
        client_process_out = sp.DEVNULL
    else:
        logging.info(f'Writing client output into {client_output.absolute()}')
        client_process_out = open(client_output, 'a+')
        client_process_out.write(f'Started daq-client on {ctime()}')
    client_process = sp.Popen(
        [daq_client_path, '-p', str(netcfg['client']['port'])],
        stdout=client_process_out)
    daq_coordinator = DAQCoordinator(netcfg, capture_data)
    logging.info('DAQ-Coordinator initialized')
    try:
        daq_coordinator.run()
    except KeyboardInterrupt:
        client_process.kill()
        if client_output is not None:
            client_process_out.close()
        sys.exit(1)
    client_process.kill()
    if client_output is not None:
        client_process_out.close()
