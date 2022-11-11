class ConfigPatchError(Exception):
    def __init__(self, message):
        self.message = message


class ConfigFormatError(Exception):
    def __init__(self, message):
        self.message = message
