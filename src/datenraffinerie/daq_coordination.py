import zmq
import sys
import bson
import yaml
import logging
import click
from pathlib import Path
from .control_adapter import DAQSystem
from hgcroc_configuration_client.client import Client as SCClient
from Schema import Schema, Or
from .errors import DAQError
import uuid


class DAQCoordCommand():
    valid_commands = ['aquire lock', 'release lock',
                      'initialize', 'measure', 'shutdown']
    schema = Schema(Or({
        'command': Or('aquire lock', 'shutdown'),
        'locking_token': None,
        'config': None
        }, {
        'command': 'release_lock',
        'locking_token': str,
        'config': None
        }, {
        'command': Or('load defaults', 'measure'),
        'locking_token': str,
        'config': dict
        }))

    def __init__(self, command: str, locking_token=None,
                 config=None):
        self.command = command if command in self.vaild_commands else None
        if command in self.valid_commands[1:] and locking_token is None:
            raise DAQError(f"For a message with the command: {command}, a "
                           "locking token is required")
        self.locking_token = locking_token
        if command in self.valid_commands[2:] and config is None:
            raise DAQError("For a message of type 'load defaults'"
                           "or 'measure' a configuration dict is required")
        self.config = config

    def serialize(self):
        return bson.dumps({'command': self.command,
                           'locking_token': self.locking_token,
                           'config': self.config})

    @staticmethod
    def parse(message: bytes):
        try:
            message_dict = bson.loads(message)
        except:
            raise DAQError('Unable to decode bson message')
        valid_message = DAQCoordCommand.schema.validate(message_dict)
        return DAQCoordCommand(command=valid_message['command'],
                               locking_token=valid_message['locking_token'],
                               config=valid_message['config'])


class DAQCoordResponse():
    valid_responses = ['error', 'data', 'lock', 'ack', 'access denied']
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
        })
    )

    def __init__(self, type: str, content=None):
        if type not in self.valid_responses:
            raise DAQError('daq response not valid')
        self.type = type
        self.content = content
        if type == 'data' and not isinstance(content, bytes):
            raise DAQError('The data needs to be of type bytes')

    def serialize(self):
        if self.type == 'error' and self.error is not None:
            return bson.dumps({'type': 'error', 'content': self.error})
        else:
            raise DAQError('daq error response was attempted but'
                           'no error was given')
        if self.type == 'data' and self.data is not None:
            return bson.dumps({'type': 'data', 'content': self.data})
        else:
            raise DAQError('No data provided to the daq response')
        if self.type == 'lock':
            return bson.dumps({'type': 'lock', 'content': self.lock})
        if type == 'ack':
            return bson.dumps({'type': 'ack', 'content': None})

    @staticmethod
    def parse(message: bytes):
        try:
            dict = bson.loads(message)
        except:
            raise DAQError('Unable to decode bson message')
        valid_message = DAQCoordResponse.schema.validate(dict)
        return DAQCoordResponse(type=valid_message['type'],
                                content=valid_message['content'])


class DAQCoordinator():

    def __init__(self, network_config):
        self.network_config = network_config
        self.logger = logging.getLogger('daq_coordinator')
        self.logger.debug('created the target and daq systems')
        self.lock = None
        self.initialized = False
        self.measurement_data_path = Path('tmp/measurement_data.raw')

    def run(self):
        self.logger.debug('creating zmq context and socket')
        self.io_context = zmq.Context()
        self.command_socket = self.io_context.socket(zmq.REP)
        socket_address = \
            f"tcp://{self.network_config['daq_coordinator']['hostname']}:" +\
            f"{self.network_config['daq_coordinator']['port']}"
        self.command_socket.bind(socket_address)
        self.logger.debug('bound to: %s' % socket_address)
        self.target = SCClient(
                self.network_config['target']['hostname'],
                self.network_config['target']['port'])
        self.daq_system = DAQSystem(
                self.network_config['server']['hostname'],
                self.network_config['server']['port'],
                self.network_config['client']['hostname'],
                self.network_config['client']['port'])
        while True:
            message = self.command_socket.recv()
            daq_response = None
            try:
                daq_command = DAQCoordCommand.parse(message)
                command = daq_command['command']
                self.logger.info(f'Received a {command} command')
            except DAQError as e:
                self.logger.info('Received invalid command')
                daq_response = DAQCoordResponse(
                    type='error',
                    content=f"Parsing of the daq_command "
                            f"{daq_command['command']} failed with "
                            f"the error: {e}")
                self.command_socket.send(daq_response.serialize())
                self.lock = None
                continue

            # check for the different kind of messages
            if command == 'aquire lock':
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
                self.command_socket.send(daq_response.serialize())
                continue

            # all messages beyond this point need a locking token to work
            # so respond with an error here if no locking token can be found
            msg_lock = message['locking_token']
            self.logger.debug('Received lock from cliend: {msg_lock}')
            if self.lock != msg_lock:
                self.logger.warn(
                        f'Lock in the message does not match {self.lock}'
                        'responing with access denied')
                daq_response = DAQCoordResponse(type='access denied')
                self.command_socket.send(daq_response.serialize())
                continue

            if command == 'release lock':
                daq_response = DAQCoordResponse(
                        type='ack',
                        content=None)
                self.lock = None
                self.logger.info('releasing lock')
                self.command_socket.send(daq_response.serialize())
                if self.initialized:
                    self.logger.info('Deinitializing DAQ system')
                    self.daq_system.tear_down_data_taking_context()
                    self.initialized = False
                continue

            if command == 'initialize':
                config = daq_command['content']
                self.logger.debug(
                        'Received initialization config:\n' +
                        yaml.dump(config))
                try:
                    self.logger.debug(
                            'Initializing DAQ-System and setting up data'
                            'taking context')
                    self.daq_system.initalize(config)
                    self.daq_system.setup_data_taking_context()
                except ValueError as err:
                    self.logger.warn(
                            'initialization of the daq system failed, received'
                            f'error: {err.argss[0]}')
                    error_msg = 'During initialization of the daq system ' + \
                                f'an error ocurred: {err.args[0]}'
                    daq_response = DAQCoordResponse(
                            type='error',
                            content=error_msg
                            )
                    self.command_socket.send(daq_response.serialize())
                    continue
                try:
                    initial_target_config = config['target']
                except KeyError:
                    initial_target_config = {}
                if initial_target_config != {}:
                    self.logger.debug('Initializing target system')
                    try:
                        self.target.set(initial_target_config, readback=True)
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
                        self.command_socket.send(daq_response.serialize())
                else:
                    self.logger.debug('No target config found, '
                                      'target initialization skipped')
                self.logger.info('DAQ-System and target initialized')
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
                    self.command_socket.send(daq_response.serialize())
                    continue
                config = daq_command['content']
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
                        self.target.set(target_config, readback=True)
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
                        self.command_socket.send(daq_response.serialize())
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
                            'Data takingfailed. Got the error: '
                            f'{err.args[0]} from the DAQ-system')
                    error_msg = \
                        'During the Data taking the DAQ system encountered' \
                        f' an error: ocurred an error ocurred: {err.args[0]}'
                    daq_response = DAQCoordResponse(
                            type='error',
                            content=error_msg
                            )
                    self.command_socket.send(daq_response.serialize())
                    continue
                with open(self.measurement_data_path, 'rb') as data_file:
                    self.logger.info('Sending Acquired data to clinet')
                    daq_response = DAQCoordResponse(
                        type='data',
                        content=data_file.read()
                    )
                    self.command_socket.send(daq_response.serialize())
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
@click.option('--log', type=click.File('a+'), default=None,
              help='Enable logging and append logs to the filename passed to '
                   'this option')
@click.option('--loglevel', default='INFO',
              type=click.Choice(['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                                case_sensitive=False))
def main(netcfg, log, loglevel):
    if log is not None:
        logging.basicConfig(filename=log, level=_log_level_dict[loglevel],
                            format='[%(asctime)s] %(levelname)s:'
                                   '%(name)-50s %(message)s')
    try:
        netcfg = yaml.safe_load(netcfg.read())
    except yaml.YAMLError as err:
        sys.exit('Error reading in the network config:\n' +
                 + str(err) + '\nexiting ..')
    daq_coordinator = DAQCoordinator(netcfg)
    daq_coordinator.run()
