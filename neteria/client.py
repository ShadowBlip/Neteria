#!/usr/bin/python
#
# Asteria
# Copyright (C) 2014, William Edwards <shadowapex@gmail.com>,
#
# This file is part of Asteria.
#
# Asteria is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Asteria is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Asteria.  If not, see <http://www.gnu.org/licenses/>.
#
# Contributor(s):
#
# William Edwards <shadowapex@gmail.com>,
#
"""This module is used to create client objects that allows sending and
receiving messages to a Neteria server.

You can run an example by running the following from the command line:
`python -m neteria.client`"""

import logging
import random
import uuid

from . import core
from .core import serialize_data
from .core import unserialize_data

from datetime import datetime
from neteria.encryption import Encryption
from pprint import pformat

try:
    from rsa import PublicKey
except:
    PublicKey = None

# Create a logger for optional handling of debug messages.
logger = logging.getLogger(__name__)


class NeteriaClient(object):

    """The primary Neteria client class handles all client functions.

    The Neteria client allows you to register and send messages to a Neteria
    server. Messages are usually dictionary objects that are serialized and
    sent over the network.

    Attributes:
      server_ip (str): When the client successfully registers with the server,
        the server's IP will be stored by the client.
      server_port (int): When the client successfully registers with the
        server, the server's port will be stored by the client.
      event_uuids (dict): A list of all events that are awaiting a response
        from the server.
      event_rollbacks (dict): A list of all events that were declared "ILLEGAL"
        by the server.
      event_notifies (dict): A list of event notifications received from the
        server.
      event_confirmations (dict): A list of events that were confirmed as
        "LEGAL" by the server.
      cuuid (str): The universally unique identifier of the client.

    Args:
      version (str): A version number of your client that will be sent to the
        server upon registration. This can be used to enable backward
        compatability of your server application. Defaults to "1.0"
      client_address (str): The address for the client to listen on. Defaults
        to all addresses.
      client_port (int): The port that the client will listen on and send
        messages from. Defaults to a random port between 50000 and 60000.
      server_port (int): The server port that the client will attempt to
        register with and communicate on. Defaults to port 40850.
      compression (boolean): Whether or not compression should be enabled.
        Compression is done on all messages with zlib compression. Defaults
        to "False".
      encryption (boolean): Whether or not encryption should be enabled.
        Encryption is done on all messages with RSA encryption. Defaults to
        "False".
      timeout (float): The amount of time to wait in seconds for a confirmation
        before retrying to send the message. Defaults to 2.0 seconds.
      max_retries (int): The maximum number of retry attempts the server should
        try before considering the message has failed. Defaults to 4.
      stats (boolean): Whether or not to keep track of network statistics
        such as total bytes sent/recieved. Defaults to False.


    Examples:
      >>> import neteria.client
      >>>
      >>> myclient = neteria.client.NeteriaClient()
      >>> myclient.listen()
      Listening on port 51280 ...
      >>> myclient.autodiscover()

    """

    def __init__(self, version="1.0.2", client_address='', client_port=None,
                 server_port=40080, compression=False, encryption=False,
                 timeout=2.0, max_retries=4, stats=False):
        self.version = version
        self.client_port = client_port
        self.server = None
        self.server_key = None      # Used to hold the public key of the server
        self.server_ip = None
        self.server_port = server_port
        self.autoregistering = False  # Whether or not to auto-register.
        self.discovered_servers = {}  # List of discovered servers.
        self.event_uuids = {}
        self.event_rollbacks = {}
        self.event_notifies = {}    # Notify events buffer received from server
        self.event_confirmations = {}   # Legal high priority events buffer

        # Enable packet compression
        self.compression = compression

        # Generate a keypair if encryption is enabled
        if encryption:
            self.encryption = Encryption()
        else:
            self.encryption = False

        # Handle client registration
        self.registered = False
        self.register_retries = 0   # This is the current register retry

        # If no client port was specified, choose a random high level port.
        if not client_port:
            self.client_port = random.randrange(50000, 60000)

        # Check to see if we have generated a uuid or not. If not, generate
        # one.
        self.cuuid = uuid.uuid1()

        # Create a listener object that we can use to send and receive
        # messages.
        self.listener = core.ListenerUDP(self, listen_address=client_address,
                                         listen_port=self.client_port,
                                         stats=stats)

        # Set a timeout and maximum number of retries for responses from the
        # server.
        self.timeout = timeout
        self.max_retries = max_retries


    def listen(self):
        """Starts the client listener to listen for server responses.

        Args:
          None

        Returns:
          None

        """

        logger.info("Listening on port " + str(self.listener.listen_port))
        self.listener.listen()


    def retransmit(self, data):
        """Processes messages that have been delivered from the transport
        protocol.

        Args:
          data (dict): A dictionary containing the packet data to resend.

        Returns:
          None

        Examples:
          >>> data
          {'method': 'REGISTER', 'address': ('192.168.0.20', 40080)}

        """

        # Handle retransmitting REGISTER requests if we don't hear back from
        # the server.
        if data["method"] == "REGISTER":
            if not self.registered and self.register_retries < self.max_retries:
                logger.debug("<%s> Timeout exceeded. " % str(self.cuuid) + \
                              "Retransmitting REGISTER request.")
                self.register_retries += 1
                self.register(data["address"], retry=False)
            else:
                logger.debug("<%s> No need to retransmit." % str(self.cuuid))

        if data["method"] == "EVENT":
            if data["euuid"] in self.event_uuids:
                # Increment the current retry count of the euuid
                self.event_uuids[data["euuid"]]["retry"] += 1

                if self.event_uuids[data["euuid"]]["retry"] > self.max_retries:
                    logger.debug("<%s> Max retries exceeded. Timed out waiting "
                                  "for server for event: %s" % (data["cuuid"],
                                                                data["euuid"]))
                    logger.debug("<%s> <euuid:%s> Deleting event from currently "
                                  "processing event uuids" % (data["cuuid"],
                                                              str(data["euuid"])))
                    del self.event_uuids[data["euuid"]]
                else:
                    # Retransmit that shit
                    self.listener.send_datagram(
                        serialize_data(data, self.compression,
                                       self.encryption, self.server_key),
                        self.server)

                    # Then we set another schedule to check again
                    logger.debug("<%s> <euuid:%s> Scheduling to retry in %s "
                                  "seconds" % (data["cuuid"],
                                               str(data["euuid"]),
                                               str(self.timeout)))
                    self.listener.call_later(
                        self.timeout, self.retransmit, data)
            else:
                logger.debug("<%s> <euuid:%s> No need to "
                              "retransmit." % (str(self.cuuid),
                                               str(data["euuid"])))


    def handle_message(self, msg, host):
        """Processes messages that have been delivered from the transport
        protocol

        Args:
          msg (string): The raw packet data delivered from the transport
            protocol.
          host (tuple): A tuple containing the (address, port) combination of
            the message's origin.

        Returns:
          A formatted response to the client with the results of the processed
          message.

        Examples:
          >>> msg
          {"method": "OHAI Client", "version": "1.0"}
          >>> host
          ('192.168.0.20', 36545)

        """

        logger.debug("Executing handle_message method.")
        response = None

        # Unserialize the data packet
        # If encryption is enabled, and we've receive the server's public key
        # already, try to decrypt
        if self.encryption and self.server_key:
            msg_data = unserialize_data(msg, self.compression, self.encryption)
        else:
            msg_data = unserialize_data(msg, self.compression)

        # Log the packet
        logger.debug("Packet received: " + pformat(msg_data))

        # If the message data is blank, return none
        if not msg_data:
            return response

        if "method" in msg_data:
            if msg_data["method"] == "OHAI Client":
                logger.debug("<%s> Autodiscover response from server received "
                              "from: %s" % (self.cuuid, host[0]))
                self.discovered_servers[host]= [msg_data["version"], msg_data["server_name"]]
                # Try to register with the discovered server
                if self.autoregistering:
                    self.register(host)
                    self.autoregistering = False

            elif msg_data["method"] == "NOTIFY":
                self.event_notifies[msg_data["euuid"]] = msg_data["event_data"]
                logger.debug("<%s> Notify received" % self.cuuid)
                logger.debug("<%s> Notify event buffer: %s" % (self.cuuid,
                    pformat(self.event_notifies)))

                # Send an OK NOTIFY to the server confirming we got the message
                response = serialize_data(
                    {"cuuid": str(self.cuuid),
                     "method": "OK NOTIFY",
                     "euuid": msg_data["euuid"]},
                    self.compression, self.encryption, self.server_key)

            elif msg_data["method"] == "OK REGISTER":
                logger.debug("<%s> Ok register received" % self.cuuid)
                self.registered = True
                self.server = host

                # If the server sent us their public key, store it
                if "encryption" in msg_data and self.encryption:
                    self.server_key = PublicKey(
                        msg_data["encryption"][0], msg_data["encryption"][1])

            elif (msg_data["method"] == "LEGAL" or
                  msg_data["method"] == "ILLEGAL"):
                logger.debug("<%s> Legality message received" % str(self.cuuid))
                self.legal_check(msg_data)

                # Send an OK EVENT response to the server confirming we
                # received the message
                response = serialize_data(
                    {"cuuid": str(self.cuuid),
                     "method": "OK EVENT",
                     "euuid": msg_data["euuid"]},
                    self.compression, self.encryption, self.server_key)

        logger.debug("Packet processing completed")

        return response


    def autodiscover(self, autoregister=True):
        """This function will send out an autodiscover broadcast to find a
        Neteria server. Any servers that respond with an "OHAI CLIENT"
        packet are servers that we can connect to. Servers that respond are
        stored in the "discovered_servers" list.

        Args:
          autoregister (boolean): Whether or not to automatically register
            with any responding servers. Defaults to True.

        Returns:
          None

        Examples:
          >>> myclient = neteria.client.NeteriaClient()
          >>> myclient.listen()
          >>> myclient.autodiscover()
          >>> myclient.discovered_servers
          {('192.168.0.20', 40080): u'1.0', ('192.168.0.82', 40080): '2.0'}

        """

        logger.debug("<%s> Sending autodiscover message to broadcast "
                      "address" % str(self.cuuid))
        if not self.listener.listening:
            logger.warning("Neteria client is not listening. The client "
                   "will not be able to process responses from the server")
        message = serialize_data(
            {"method": "OHAI",
             "version": self.version,
             "cuuid": str(self.cuuid)},
            self.compression, encryption=False)
        if autoregister:
            self.autoregistering = True

        self.listener.send_datagram(
            message, ("<broadcast>", self.server_port), message_type="broadcast")


    def register(self, address, retry=True):
        """This function will send a register packet to the discovered Neteria
        server.

        Args:
          address (tuple): A tuple of the (address, port) to send the register
            request to.
          retry (boolean): Whether or not we want to reset the current number
            of registration retries to 0.

        Returns:
          None

        Examples:
          >>> address
          ('192.168.0.20', 40080)

        """

        logger.debug("<%s> Sending REGISTER request to: %s" % (str(self.cuuid),
                                                                str(address)))
        if not self.listener.listening:
            logger.warning("Neteria client is not listening.")

        # Construct the message to send
        message = {"method": "REGISTER", "cuuid": str(self.cuuid)}

        # If we have encryption enabled, send our public key with our REGISTER
        # request
        if self.encryption:
            message["encryption"] = [self.encryption.n, self.encryption.e]

        # Send a REGISTER to the server
        self.listener.send_datagram(
            serialize_data(message, self.compression,
                           encryption=False), address)

        if retry:
            # Reset the current number of REGISTER retries
            self.register_retries = 0

        # Schedule a task to run in x seconds to check to see if we've timed
        # out in receiving a response from the server
        self.listener.call_later(
            self.timeout, self.retransmit, {"method": "REGISTER",
                                            "address": address})


    def event(self, event_data, priority="normal"):
        """This function will send event packets to the server. This is the
        main method you would use to send data from your application to the
        server.

        Whenever an event is sent to the server, a universally unique event id
        (euuid) is created for each event and stored in the "event_uuids"
        dictionary. This dictionary contains a list of all events that are
        currently waiting for a response from the server. The event will only
        be removed from this dictionary if the server responds with LEGAL or
        ILLEGAL or if the request times out.

        Args:
          event_data (dict): The event data to send to the server. This data
            will be passed through the server's middleware to determine if the
            event is legal or not, and then processed by the server it is legal
          priority (string): The event's priority informs the server of whether
            or not the client is going to wait for a confirmation message from
            the server indicating whether its event was LEGAL or ILLEGAL.
            Setting this to "normal" informs the server that the client will
            wait for a response from the server before processing the event.
            Setting this to "high" informs the server that the client will NOT
            wait for a response. Defaults to "normal".

        Returns:
          A universally unique identifier (uuid) of the event.

        Examples:
          >>> event_data
          >>> priority

        """

        logger.debug("event: " + str(event_data))

        # Generate an event UUID for this event
        euuid = uuid.uuid1()
        logger.debug("<%s> <euuid:%s> Sending event data to server: "
               "%s" % (str(self.cuuid), str(euuid), str(self.server)))
        if not self.listener.listening:
            logger.warning("Neteria client is not listening.")

        # If we're not even registered, don't even bother.
        if not self.registered:
            logger.warning("<%s> <euuid:%s> Client is currently not registered. "
                            "Event not sent." % (str(self.cuuid), str(euuid)))
            return False

        # Send the event data to the server
        packet = {"method": "EVENT",
                  "cuuid": str(self.cuuid),
                  "euuid": str(euuid),
                  "event_data": event_data,
                  "timestamp": str(datetime.now()),
                  "retry": 0,
                  "priority": priority}

        self.listener.send_datagram(
            serialize_data(packet, self.compression,
                           self.encryption, self.server_key),
            self.server)

        logger.debug("<%s> Sending EVENT Packet: %s" % (str(self.cuuid),
                                                         pformat(packet)))

        # Set the sent event to our event buffer to see if we need to roll back
        # or anything
        self.event_uuids[str(euuid)] = packet

        # Now we need to reschedule a timeout/retransmit check
        logger.debug("<%s> Scheduling retry in %s seconds" % (str(self.cuuid),
                                                               str(self.timeout)))
        self.listener.call_later(self.timeout, self.retransmit, packet)

        return euuid


    def legal_check(self, message):
        """This method handles event legality check messages from the server.

        Args:
          message (dict): The unserialized legality dictionary received from
            the server.

        Returns:
          None

        Examples:
          >>> message

        """

        # If the event was legal, remove it from our event buffer
        if message["method"] == "LEGAL":
            logger.debug("<%s> <euuid:%s> Event LEGAL" % (str(self.cuuid),
                                                           message["euuid"]))
            logger.debug("<%s> <euuid:%s> Removing event from event "
                   "buffer." % (str(self.cuuid), message["euuid"]))

            # If the message was a high priority, then we keep track of legal
            # events too
            if message["priority"] == "high":
                self.event_confirmations[
                    message["euuid"]] = self.event_uuids[message["euuid"]]
                logger.debug("<%s> <euuid:%s> Event was high priority. Adding "
                              "to confirmations buffer." % (str(self.cuuid),
                                                            message["euuid"]))
                logger.debug("<%s> <euuid:%s> Current event confirmation "
                              "buffer: %s" % (str(self.cuuid),
                                              message["euuid"],
                                              pformat(self.event_confirmations)))

            # Try and remove the event from the currently processing events
            try:
                del self.event_uuids[message["euuid"]]
            except KeyError:
                logger.warning("<%s> <euuid:%s> Euuid does not exist in event "
                               "buffer. Key was removed before we could process "
                               "it." % (str(self.cuuid), message["euuid"]))

        # If the event was illegal, remove it from our event buffer and add it
        # to our rollback list
        elif message["method"] == "ILLEGAL":
            logger.debug("<%s> <euuid:%s> Event ILLEGAL" % (str(self.cuuid),
                                                            message["euuid"]))
            logger.debug("<%s> <euuid:%s> Removing event from event buffer and "
                         "adding to rollback buffer." % (str(self.cuuid),
                                                         message["euuid"]))
            self.event_rollbacks[
                message["euuid"]] = self.event_uuids[message["euuid"]]
            del self.event_uuids[message["euuid"]]


# For testing you can run:
# sudo sendip -p ipv4 -is 127.0.0.1 -p udp -us 5070 -ud 10858 -d
# '{"method": "OHAI"}' -v 127.0.0.1
if __name__ == '__main__':

    # Enable logging for our client.
    import sys
    logger = logging.getLogger('neteria.client')
    logger.setLevel(logging.DEBUG)
    log_hdlr = logging.StreamHandler(sys.stdout)
    log_hdlr.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_hdlr.setFormatter(formatter)
    logger.addHandler(log_hdlr)
    logger.info("Client Started")

    # Create an instance of our client.
    client = NeteriaClient()
    client.listen()

    client.autodiscover()
    raw_input("enter to exit...")
