import pyyaml as yaml


class HexacontrollerProtocol(object):
    reply_string = ''
    type = ''

    def __init__(self, transport):
        self.transport = transport

    def write(self, parameters: dict):
        config_str = yaml.safe_dump(dict)
        reply = self.transport.write('configure')
        if "ready" not in reply.lower():
            raise ValueError(
                    f"The configuration cannot be "
                    f" written to {self.transport.hostname}. The target"
                    f"responded with {reply}")
        reply = self.transport.write(config_str)
        if reply != self.reply_string:
            raise ValueError(f"Configuration of the {self.type} failed")

    def reset(self):
        self.transport.reset()


class HexcontrollerConfigProtocol(HexacontrollerProtocol):
    reply_string = 'Configured'
    type = 'daq endpoint'


class HexaboardConfigProtocol(HexacontrollerProtocol):
    reply_string = 'ROC(s) CONFIGURED\n...\n'
    type = 'target'
