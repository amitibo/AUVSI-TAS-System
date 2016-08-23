from twisted.internet import reactor, protocol
from twisted.protocols.basic import LineReceiver
from twisted.python import log
import global_settings as gs
import json
import os



class ControlProtocol(LineReceiver):
    """Protocol for communicating with the remote server on the onboard computer"""

    def connectionMade(self):
        self.factory.on_connection(self)

    def connectionLost(self, reason):
        self.factory.on_disconnection(reason)

    def lineReceived(self, line):
        self.factory.app.log_message(line)


class ControlServerFactory(protocol.ReconnectingClientFactory):
    protocol = ControlProtocol
    downloading_flag = False

    #
    # Reconnection parameters.
    #
    maxDelay = 1
    initialDelay = 0.1

    def __init__(
        self,
        app
        ):

        self.app = app
        self.client_instance = None

    def on_connection(self, instance):
        """Handle connection to remote server."""

        self.client_instance = instance

        #
        # Notify the GUI application.
        #
        self.app.on_connection()

    def on_disconnection(self, conn):
        """Handle disconnection to remote server."""

        self.client_instance = None

        #
        # Notify the GUI application.
        #
        self.app.on_disconnection()

    def send_cmd(self, cmd, *params, **kwds):
        if self.client_instance is None:
            return

        if _server_params['role'] != gs.PRIMARY and not cmd.startswith('crop') and not cmd == gs.STATE:
            log.msg("You are not primary, you can't do '{}'".format(cmd))
            return

        cmd_line = cmd
        if params:
            cmd_line = cmd_line + ' ' + ' '.join([str(param) for param in params])
        if kwds:
            cmd_line = cmd_line + ' ' + ' '.join(['{k} {v}'.format(k=k, v=v) for k, v in kwds.items()])

        log.msg('Sending cmd: {cmd_line}'.format(cmd_line=cmd_line))

        self.client_instance.sendLine(cmd_line)


def setserver(ip, role, ip_controller):
    """Set the server address"""

    global _server_params
    _server_params = {'ip': ip, 'role': role, 'ip_controller':ip_controller}


_control_server = None
_images_client = None

def getClient():
    global _images_client
    return _images_client

def connect(app, images_client):
    """Start the twisted server."""

    global _control_server
    global _images_client

    if _control_server is not None:
        _control_server.stopTrying()
    if _images_client is not None:
        _images_client.shutdown()

    #
    # Setup the control server
    #
    _control_server = ControlServerFactory(app)
    reactor.connectTCP(
        _server_params['ip'],
        gs.CAMERA_CTL_PORT,
        _control_server
    )

    #
    # Setup the Images client.
    #
    _images_client = images_client(
        app,
        ip_camera=_server_params['ip'],
        role=_server_params['role'],
        ip_controller=_server_params['ip_controller'],
    )

    return _control_server
