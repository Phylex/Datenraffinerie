class OutputError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class DAQError(Exception):
    def __init__(self, message):
        self.message = message

class DAQConfigError(Exception):
    def __init__(self, message):
        self.message = message


