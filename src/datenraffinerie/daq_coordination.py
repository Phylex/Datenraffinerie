import zmq
import bson
import logging
from pathlib import Path
from . import control_adapter as ctrl
from Schema import Schema, Or
from .errors import DAQError
import uuid


logging.basicConfig(filename='daq_coordinator.log',
                    filemode='w',
                    encoding='utf-8',
                    level=logging.DEBUG)


class DAQCoordCommand():
    valid_commands = ['aquire lock', 'release lock',
                      'load defaults', 'measure', 'shutdown']
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
            raise DAQError('daq error response was attempted but no error was given')
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
        self.measurement_data_path = Path('tmp/measurement_data.raw')

    def run(self):
        self.logger.debug('creating zmq context and socket')
        self.io_context = zmq.Context()
        self.command_socket = self.io_context.socket(zmq.REP)
        socket_address = f"tcp://{self.network_config['daq_coordinator']['hostname']}:" +\
                         f"{self.network_config['daq_coordinator']['port']}"
        self.command_socket.bind(socket_address)
        self.logger.debug('bound to: %s' % socket_address)
        self.target = ctrl.TargetAdapter(self.network_config['target']['hostname'],
                                         self.network_config['target']['port'])
        self.daq_system = ctrl.DAQSystem(self.network_config['server']['hostname'],
                                         self.network_config['server']['port'],
                                         self.network_config['client']['hostname'],
                                         self.network_config['client']['port'])

        while True:
            message = self.command_socket.recv()
            daq_response = None
            try:
                daq_command = DAQCoordCommand.parse(message)
                command = daq_command['command']
            except DAQError as e:
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
                    daq_response = DAQCoordResponse(type='lock',
                                                    content=self.lock)
                else:
                    daq_response = DAQCoordResponse(type='lock',
                                                    content=None)
            else:
                if self.lock != message['locking_token']:
                    daq_response = DAQCoordResponse(type='access denied')
                    self.command_socket.send(daq_response.serialize())
                    continue

            if command == 'release lock':
                if self.lock is None:
                    daq_response = DAQCoordResponse(
                            type='error',
                            content='Coordinator not locked')
                else:
                    daq_response = DAQCoordResponse(
                            type='ack',
                            content=None)

            if command == 'load defaults':
                if message['locking_token'] != self.lock:
                    daq_response
                try:
                    config = daq_command['content']
                    daq_config = config['daq']
                    target_config = config['target']
                    self.target.configure(target_config)
                    self.daq_system.configure(daq_config)
                except KeyError:
                    daq_response = DAQCoordResponse(
                        type='error',
                        content='Configuration did not have a daq or target field')
                    self.command_socket.send(daq_response.serialize())
                    continue
                daq_response = DAQCoordResponse(
                        type='ack',
                        content=None
                )

            if command == 'measure':
                config = daq_config['content']
                try:
                    target_config = config['target']
                except KeyError:
                    target_config = {}
                try:
                    daq_config = config['daq']
                except KeyError:
                    daq_config = {}
                if not self.target.has_default()\
                   and not self.daq_system.has_default():
                    daq_response = DAQCoordResponse(
                        type='error',
                        content='Target or daq system are not loaded'
                    )
                    self.command_socket.send(daq_response.serialize())
                    continue
                self.target.configure(target_config)
                self.daq_system.configure(daq_config)
                self.daq_system.take_data(self.measurement_data_path)
                with open(self.measurement_data_path, 'rb') as data_file:
                    daq_response = DAQCoordResponse(
                        type='data',
                        content=data_file.read()
                    )
            self.command_socket.send(daq_response.serialize())
