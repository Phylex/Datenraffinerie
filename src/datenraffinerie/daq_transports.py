import zmq


class ZMQ_control_transport(object):
    """
    This transport is the way that the Datenraffinerie connects to
    the backend. This encapsulates the creation of the connection
    and the sending of string messages
    """

    def __init__(self, remote_host, remote_port,
                 logger=None, timeout: int = None):
        self.hostname = remote_host
        self.port = remote_port
        self.timeout = timeout
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
        self.logger = logger

    def write(self, message: str):
        """
        The write method starts a transaction between the frontend and the
        backend. The frontend sends a request (with the ZMQ REP/REQ pattern)
        and the backend responds. It is up to the protocol to determin The
        message sent and interpret the response
        """
        if self.logger is not None:
            self.logger.debug(
                    f"Sending string '{message}'"
                    f" to {self.hostname}:{self.port}")
        self.socket.send_string(message)
        rep = self.socket.recv_string()
        if self.logger is not None:
            self.logger.debug(
                    "Received string '{rep}' from "
                    f"{self.hostname}:{self.port}")
        return rep

    def reset(self):
        self.socket.close()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.hostname}:{self.port}")
