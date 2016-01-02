#!/usr/bin/python
#
# Neteria
# Copyright (C) 2014, William Edwards <shadowapex@gmail.com>,
#
# This file is part of Neteria.
#
# Neteria is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neteria is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neteria.  If not, see <http://www.gnu.org/licenses/>.
#
# Contributor(s):
#
# William Edwards <shadowapex@gmail.com>
#
"""The server module provides a way to send and receive messages to clients
and process incoming messages.

Since the Neteria server inherently does not trust the clients, each message
received will go through a "middleware" layer which decides whether
or not a message received from a client is legal or not.

If the message is LEGAL, it will send the message to your application's
"middleware" which will carry out legal actions in your application.

If the message was deamed ILLEGAL, it will respond to the client indicating
that the action was illegal, and discard the message without further
processing.

You can run an example by running the following from the command line:
`python -m neteria.server`"""

import logging
import threading
import uuid

from datetime import datetime
from pprint import pformat
from rsa import PublicKey

from .core import serialize_data
from .core import unserialize_data
from .core import ListenerUDP
from .encryption import Encryption

# Create a logger for optional handling of debug messages.
logger = logging.getLogger(__name__)


class NeteriaServer(object):
    """The primary Neteria Server class handles all server functions.

    Args:
      middleware (tools._Middleware): The middleware object used to determine
        if an event recieved by the client is LEGAL or not. It will also
        execute the event in your application if the event was LEGAL.
      version (string): The version of your application. This can be used
        to handle clients of different versions differently. Defaults to "1.0".
      app (object): The instance of your application. Setting this will
        automatically set the app.server attribute to an instance of this
        class. Defaults to None.
      port (int): The UDP port for the server to listen on. Defaults to 40080.
      compression (boolean): Whether or not to enable zlib compression on all
        network traffic. Defaults to False.
      encryption (boolean): Whether or not to enable RSA encryption on traffic
        to the client. Defaults to False.
      timeout (float): The amount of time to wait in seconds for a confirmation
        before retrying to send the message. Defaults to 2.0 seconds.
      max_retries (int): The maximum number of retry attempts the server should
        try before considering the message has failed. Defaults to 4.
      registration_limit (int): The maximum number of clients that can be
        connected and registered with the server. Defaults to 50.
      stats (boolean): Whether or not to keep track of network statistics
        such as total bytes sent/recieved. Defaults to False.

    Examples:
      >>> from neteria.tools import _Middleware
      >>> from neteria.server import NeteriaServer
      >>>
      >>> middleware = _Middleware()
      >>> myserver = NeteriaServer(middleware)
      >>> myserver.listen()

    """

    def __init__(self, middleware, version="1.0.2", app=None, server_address='',
                 server_port=40080, server_name=None, compression=False, encryption=False,
                 timeout=2.0, max_retries=4, registration_limit=50, stats=False):
        self.version = version
        self.allowed_versions = [
            version]   # Client versions allowed to register.
        self.event_uuids = {}
        self.middleware = middleware
        self.port = server_port
        self.server_name = server_name
        self.compression = compression

        # Generate a keypair if encryption is enabled
        if encryption:
            self.encryption = Encryption()
        else:
            self.encryption = False

        # Keep a separate key pair that matches hosts to cuuid to find their
        # public key.
        self.encrypted_hosts = {}

        # Provide access to the app the created the server class.
        self.app = app

        # Provide the middleware with this instance of Neteria Server
        self.middleware.server = self

        # Create a listener to allow us to send and recieve messages.
        self.listener = ListenerUDP(self, listen_address=server_address,
                                    listen_port=server_port, stats=stats)

        # Set a timeout and maximum number of retries for responses from
        # clients.
        self.timeout = timeout
        self.max_retries = max_retries

        # Set a limit on the number of registrations to prevent registration
        # attacks.
        self.registration_limit = registration_limit
        self.registry = {}


    def listen(self):
        """Starts the server listener to listen for client messages.

        Args:
          None

        Returns:
          None

        """

        logger.info("Listening on port " + str(self.listener.listen_port))
        self.listener.listen()


    def retransmit(self, data):
        """Processes messages that have been delivered from the listener.

        Args:
          data (dict): A dictionary containing the uuid, euuid, and message
            response. E.g. {"cuuid": x, "euuid": y, "response": z}.

        Returns:
          None

        """

        # If that shit is still in self.event_uuids, then that means we STILL
        # haven't gotten a response from the client. Then we resend that shit
        # and WAIT
        if data["euuid"] in self.event_uuids:
            # Increment the current retry count of the euuid
            self.event_uuids[data["euuid"]] += 1

            # If we've tried more than the maximum, just log an error
            # and stahap.
            if (self.event_uuids[data["euuid"]] > self.max_retries or
                    data["cuuid"] not in self.registry):
                logger.warning("<%s> Retry limit exceeded. "
                               "Timed out waiting for client for "
                               "event: %s" % (data["cuuid"], data["euuid"]))
                logger.warning("<%s> Deleting event from currently processing "
                               "event uuids" % data["cuuid"])
                del self.event_uuids[data["euuid"]]
            else:
                # Retransmit that shit
                logger.debug("<%s> Timed out waiting for response. Retry %s. "
                             "Retransmitting message: "
                             "%s" % (data["cuuid"],
                                     pformat(self.event_uuids[data["euuid"]]),
                                     data["response"]))

                # Look up the host and port based on cuuid
                host = self.registry[data["cuuid"]]["host"]
                port = self.registry[data["cuuid"]]["port"]

                # Send the packet to the client
                self.listener.send_datagram(data["response"], (host, port))

                # Then we set another schedule to check again
                logger.debug("<%s> Scheduling to retry in %s "
                             "seconds" % (data["cuuid"], str(self.timeout)))
                self.listener.call_later(self.timeout, self.retransmit, data)


    def handle_message(self, msg, host):
        """Processes messages that have been delivered from the listener.

        Args:
          msg (string): The raw packet data delivered from the listener. This
            data will be unserialized and then processed based on the packet's
            method.
          host (tuple): The (address, host) tuple of the source message.

        Returns:
          A response that will be sent back to the client via the listener.

        """

        response = None

        # Unserialize the packet, and decrypt if the host has encryption enabled
        if host in self.encrypted_hosts:
            msg_data = unserialize_data(msg, self.compression, self.encryption)
        else:
            msg_data = unserialize_data(msg, self.compression)

        logger.debug("Packet received: " + pformat(msg_data))

        # If the message data is blank, return none
        if not msg_data: return response

        # For debug purposes, check if the client is registered or not
        if self.is_registered(msg_data["cuuid"], host[0]):
            logger.debug("<%s> Client is currently registered" % msg_data["cuuid"])
        else:
            logger.debug("<%s> Client is not registered"  % msg_data["cuuid"])

        if "method" in msg_data:
            if msg_data["method"] == "REGISTER":
                logger.debug("<%s> Register packet received" % msg_data["cuuid"])
                response = self.register(msg_data, host)

            elif msg_data["method"] == "OHAI":
                logger.debug("<%s> Autodiscover packet received" % msg_data["cuuid"])
                response = self.autodiscover(msg_data)

            elif msg_data["method"] == "EVENT":
                logger.debug("<%s> <euuid:%s> Event message "
                             "received" % (msg_data["cuuid"], msg_data["euuid"]))
                response = self.event(msg_data["cuuid"],
                                      host,
                                      msg_data["euuid"],
                                      msg_data["event_data"],
                                      msg_data["timestamp"],
                                      msg_data["priority"])

            elif msg_data["method"] == "OK EVENT":
                logger.debug("<%s> <euuid:%s> Event confirmation message "
                             "received" % (msg_data["cuuid"], msg_data["euuid"]))
                try:
                    del self.event_uuids[msg_data["euuid"]]
                except KeyError:
                    logger.warning("<%s> <euuid:%s> Euuid does not exist in event "
                                   "buffer. Key was removed before we could process "
                                   "it." % (msg_data["cuuid"], msg_data["euuid"]))

            elif msg_data["method"] == "OK NOTIFY":
                logger.debug("<%s> <euuid:%s> Ok notify "
                             "received" % (msg_data["cuuid"], msg_data["euuid"]))
                try:
                    del self.event_uuids[msg_data["euuid"]]
                except KeyError:
                    logger.warning("<%s> <euuid:%s> Euuid does not exist in event "
                                   "buffer. Key was removed before we could process "
                                   "it." % (msg_data["cuuid"], msg_data["euuid"]))


        logger.debug("Packet processing completed")
        return response


    def autodiscover(self, message):
        """This function simply returns the server version number as a response
        to the client.

        Args:
          message (dict): A dictionary of the autodiscover message from the
            client.

        Returns:
          A JSON string of the "OHAI Client" server response with the server's
          version number.

        Examples:
          >>> response
          '{"method": "OHAI Client", "version": "1.0"}'

        """
        # Check to see if the client's version is the same as our own.
        if message["version"] in self.allowed_versions:
            logger.debug("<%s> Client version matches server "
                         "version." % message["cuuid"])
            response = serialize_data({"method": "OHAI Client",
                                       "version": self.version,
                                       "server_name": self.server_name},
                                      self.compression,
                                      encryption=False)
        else:
            logger.warning("<%s> Client version %s does not match allowed server "
                           "versions %s" % (message["cuuid"],
                                            message["version"],
                                            self.version))
            response = serialize_data({"method": "BYE REGISTER"},
                                      self.compression,
                                      encryption=False)

        return response


    def register(self, message, host):
        """This function will register a particular client in the server's
        registry dictionary.

        Any clients that are registered will be able to send and recieve events
        to and from the server.

        Args:
          message (dict): The client message from the client who wants to
            register.
          host (tuple): The (address, port) tuple of the client that is
            registering.

        Returns:
          A server response with an "OK REGISTER" if the registration was
          successful or a "BYE REGISTER" if unsuccessful.

        """
        # Get the client generated cuuid from the register message
        cuuid = message["cuuid"]

        # Check to see if we've hit the maximum number of registrations
        # If we've reached the maximum limit, return a failure response to the
        # client.
        if len(self.registry) > self.registration_limit:
            logger.warning("<%s> Registration limit exceeded" % cuuid)
            response = serialize_data({"method": "BYE REGISTER"},
                                      self.compression, encryption=False)

            return response

        # Insert a new record in the database with the client's information
        data = {"host": host[0], "port": host[1], "time": datetime.now()}

        # Prepare an OK REGISTER response to the client to let it know that it
        # has registered
        return_msg = {"method": "OK REGISTER"}

        # If the register request has a public key included in it, then include
        # it in the registry.
        if "encryption" in message and self.encryption:
            data["encryption"] = PublicKey(message["encryption"][0],
                                           message["encryption"][1])

            # Add the host to the encrypted_hosts dictionary so we know to
            # decrypt messages from this host
            self.encrypted_hosts[host] = cuuid

            # If the client requested encryption and we have it enabled, send
            # our public key to the client
            return_msg["encryption"] = [self.encryption.n, self.encryption.e]

        # Add the entry to the registry
        if cuuid in self.registry:
            for key in data:
                self.registry[cuuid][key]=data[key]
        else:
            self.registry[cuuid] = data

        # Serialize our response to the client
        response = serialize_data(return_msg,
                                  self.compression, encryption=False)

         # For debugging, print all the current rows in the registry
        logger.debug("<%s> Registry entries:" % cuuid)

        for (key, value) in self.registry.items():
            logger.debug("<%s> %s %s" % (str(cuuid), str(key), pformat(value)))

        return response


    def is_registered(self, cuuid, host):
        """This function will check to see if a given host with client uuid is
        currently registered.

        Args:
          cuuid (string): The client uuid that wishes to register.
          host (tuple): The (address, port) tuple of the client that is
            registering.

        Returns:
          Will return True if the client is registered and will return False if
          it is not.

        """
        # Check to see if the host with the client uuid exists in the registry
        # table.
        if (cuuid in self.registry) and (self.registry[cuuid]["host"] == host):
            return True
        else:
            return False


    def event(self, cuuid, host, euuid, event_data, timestamp, priority):
        """This function will process event packets and send them to legal
        checks.

        Args:
          cuuid (string): The client uuid that the event came from.
          host (tuple): The (address, port) tuple of the client.
          euuid (string): The event uuid of the specific event.
          event_data (any): The event data that we will be sending to the
            middleware to be judged and executed.
          timestamp (string): The client provided timestamp of when the event
            was created.
          priority (string): The priority of the event. This is normally set to
            either "normal" or "high". If an event was sent with a high
            priority, then the client will not wait for a response from the
            server before executing the event locally.

        Returns:
          A LEGAL/ILLEGAL response to be sent to the client.

        """

        # Set the initial response to none
        response = None

        # If the host we're sending to is using encryption, get their key to
        # encrypt.
        if host in self.encrypted_hosts:
            logger.debug("Encrypted!")
            client_key = self.registry[cuuid]["encryption"]
        else:
            logger.debug("Not encrypted :<")
            client_key = None

        # Get the port and host
        port = host[1]
        host = host[0]

        # First, we need to check if the request is coming from a registered
        # client. If it's not coming from a registered client, we tell them to
        # fuck off and register first.
        if not self.is_registered(cuuid, host):
            logger.warning("<%s> Sending BYE EVENT: Client not registered." % cuuid)
            response = serialize_data({"method": "BYE EVENT",
                                       "data": "Not registered"},
                                      self.compression,
                                      self.encryption, client_key)
            return response

        # Check our stored event uuid's to see if we're already processing
        # this event.
        if euuid in self.event_uuids:
            logger.warning("<%s> Event ID is already being processed: %s" % (cuuid,
                                                                             euuid))
            # If we're already working on this event, return none so we do not
            # reply to the client
            return response

        # If we're not already processing this event, store the event uuid
        # until we receive a confirmation from the client that it received our
        # judgement.
        self.event_uuids[euuid] = 0
        logger.debug("<%s> <euuid:%s> Currently processing events: "
                     "%s" % (cuuid, euuid, str(self.event_uuids)))
        logger.debug("<%s> <euuid:%s> New event being processed" % (cuuid, euuid))
        logger.debug("<%s> <euuid:%s> Event Data: %s" % (cuuid,
                                                         euuid,
                                                         pformat(event_data)))

        # Send the event to the game middleware to determine if the event is
        # legal or not and to process the event in the Game Server if it is
        # legal.
        if self.middleware.event_legal(cuuid, euuid, event_data):
            logger.debug("<%s> <euuid:%s> Event LEGAL. Sending judgement "
                         "to client." % (cuuid, euuid))
            response = serialize_data({"method": "LEGAL",
                                       "euuid": euuid,
                                       "priority": priority},
                                      self.compression,
                                      self.encryption, client_key)
            # Execute the event
            thread = threading.Thread(target=self.middleware.event_execute,
                                      args=(cuuid, euuid, event_data)
                                      )
            thread.start()

        else:
            logger.debug("<%s> <euuid:%s> Event ILLEGAL. Sending judgement "
                         "to client." % (cuuid, euuid))
            response = serialize_data({"method": "ILLEGAL",
                                       "euuid": euuid,
                                       "priority": priority},
                                      self.compression,
                                      self.encryption, client_key)

        # Schedule a task to run in x seconds to check to see if we've timed
        # out in receiving a response from the client.
        self.listener.call_later(self.timeout, self.retransmit,
                                 {"euuid": euuid,
                                  "response": response, "cuuid": cuuid})

        return response


    def notify(self, cuuid, event_data):
        """This function will send a NOTIFY event to a registered client.

        NOTIFY messages are nearly identical to EVENT messages, except that
        NOTIFY messages are always sent from server -> client. EVENT messages
        are always sent from client -> server. In addition to this difference,
        NOTIFY messages are not processed by a middleware to determine if
        they are legal or not, since all messages from the server should be
        considered LEGAL.

        Args:
          cuuid (string): The client uuid to send the event data to.
          event_data (any): The event data that we will be sending to the
            client.

        Returns:
          None

        """

        # Generate an event uuid for the notify event
        euuid = str(uuid.uuid1())

        # If the client uses encryption, get their key to encrypt
        if "encryption" in self.registry[cuuid]:
            client_key = self.registry[cuuid]["encryption"]
        else:
            client_key = None

        logger.debug("<%s> <%s> Sending NOTIFY event to client with event data: "
                     "%s" % (str(cuuid), str(euuid), pformat(event_data)))

        # Look up the host details based on cuuid
        try:
            ip_address = self.registry[cuuid]["host"]
        except KeyError:
            logger.warning("<%s> <%s> Host not found in registry! Transmit "
                           "Canceled" % (str(cuuid), str(euuid)))
            return False
        try:
            port = self.registry[cuuid]["port"]
        except KeyError:
            logger.warning("<%s> <%s> Port not found! Transmit "
                           "Canceled" % (str(cuuid), str(euuid)))
            return False

        # Set up the packet and address to send to
        packet = serialize_data({"method": "NOTIFY",
                                 "event_data": event_data,
                                 "euuid": euuid},
                                self.compression,
                                self.encryption, client_key)
        address = (ip_address, port)

        # If we're not already processing this event, store the event uuid
        # until we receive a confirmation from the client that it received our
        # notification.
        self.event_uuids[euuid] = 0	# This is the current retry attempt
        logger.debug("<%s> Currently processing events: "
                     "%s" % (cuuid, pformat(self.event_uuids)))
        logger.debug("<%s> New NOTIFY event being processed:" % cuuid)
        logger.debug("<%s> EUUID: %s" % (cuuid, euuid))
        logger.debug("<%s> Event Data: %s" % (cuuid, pformat(event_data)))

        # Send the packet to the client
        self.listener.send_datagram(packet, address)

        # Schedule a task to run in x seconds to check to see if we've timed
        # out in receiving a response from the client/
        self.listener.call_later(self.timeout, self.retransmit,
                                 {"euuid": euuid,
                                  "response": packet,
                                  "cuuid": cuuid})


# For testing you can run:
# sudo sendip -p ipv4 -is 127.0.0.1 -p udp -us 5070 -ud 10858 -d
# '{"method": "OHAI"}' -v 127.0.0.1
if __name__ == '__main__':

    # Enable logging for our server.
    import sys
    logger = logging.getLogger('neteria.server')
    logger.setLevel(logging.DEBUG)
    log_hdlr = logging.StreamHandler(sys.stdout)
    log_hdlr.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_hdlr.setFormatter(formatter)
    logger.addHandler(log_hdlr)
    logger.info("Server Started")

    # Import our middleware, which will process incoming events from our
    # clients.
    from tools import _Middleware
    middleware = _Middleware()

    myserver = NeteriaServer(middleware)
    myserver.listen()

    raw_input("Press enter to exit...")
