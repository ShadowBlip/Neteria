#!/usr/bin/python
#
# Asteria
# Copyright (C) 2013-2014, William Edwards <shadowapex@gmail.com>,
#                          Derek J. Clark <derekjohn.clark@gmail.com>
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
"""This module is used for the core network functionality for neteria such as
sending and receiving UDP datagrams."""

import binascii
import json
import logging
import socket
import errno
import struct
import time
import traceback
import zlib

# Create a logger for optional handling of debug messages.
logger = logging.getLogger(__name__)


def serialize_data(data, compression=False, encryption=False, public_key=None):
    """Serializes normal Python datatypes into plaintext using json.

    You may also choose to enable compression and encryption when serializing
    data to send over the network. Enabling one or both of these options will
    incur additional overhead.

    Args:
      data (dict): The data to convert into plain text using json.
      compression (boolean): True or False value on whether or not to compress
        the serialized data.
      encryption (rsa.encryption): An encryption instance used to encrypt the
        message if encryption is desired.
      public_key (str): The public key to use to encrypt if encryption is
        enabled.

    Returns:
      The string message serialized using json.

    """

    message = json.dumps(data)

    if compression:
        message = zlib.compress(message)
        message = binascii.b2a_base64(message)

    if encryption and public_key:
        message = encryption.encrypt(message, public_key)

    encoded_message = str.encode(message)

    return encoded_message

def unserialize_data(data, compression=False, encryption=False):
    """Unserializes the packet data and converts it from json format to normal
    Python datatypes.

    If you choose to enable encryption and/or compression when serializing
    data, you MUST enable the same options when unserializing data.

    Args:
      data (str): The raw, serialized packet data delivered from the transport
        protocol.
      compression (boolean): True or False value on whether or not to
        uncompress the serialized data.
      encryption (rsa.encryption): An encryption instance used to decrypt the
        message if encryption is desired.

    Returns:
      The message unserialized in normal Python datatypes.

    """
    try:
        if encryption:
            data = encryption.decrypt(data)

    except Exception as err:
        logger.error("Decryption Error: " + str(err))
        message = False
    try:
        if compression:
            data = binascii.a2b_base64(data)
            data = zlib.decompress(data)
            message = json.loads(data)

    except Exception as err:
        logger.error("Decompression Error: " + str(err))
        message = False

    decoded_message = data.decode()

    if not encryption and not compression:
        message = json.loads(decoded_message)

    return message


class ListenerUDP(object):
    """A class used to send and recieve UDP datagrams over the network.

    Args:
      app (object): A class instance with a "handle_message" method
        that will process received messages.
      threading (boolean): Whether or not to set up the main listener
        loop in its own thread. Defaults to True.
      stats (boolean): Whether or not to keep track of network statistics
        such as total bytes sent/recieved. Defaults to False.
      listen_address (str): The address for the listener to listen on,
        defaults to all addresses.
      listen_port (int): The port for the listener to listen on,
        defaults to port 40080.
      listen_type (str): The type of listener. This can be either "unicast"
        or "multicast". Unicast is designed to send messages to a single host.
        Multicast is designed to send messages to multiple hosts at once.
        Defaults to "unicast".
      bufsize (int): The size of our buffer used for receiving
        messages in bytes. If a message received is larger than this
        buffer size, the message will be truncated. Defaults to 10240.

    """

    def __init__(self, app, threading=True, stats=False, listen_address='',
                 listen_port=40080, listen_type="unicast", bufsize=10240):

        self.app = app
        self.threading = threading
        self.scheduler_thread = None
        self.listen_thread = None
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.listen_type = listen_type
        self.bufsize = bufsize
        self.listening = False

        self.stats_enabled = stats
        self.stats = {}
        self.stats['bytes_sent'] = 0
        self.stats['bytes_recieved'] = 0
        self.stats['mbps_sent'] = 0.0
        self.stats['mbps_recieved'] = 0.0
        self.stats['last_bytes_sent'] = 0
        self.stats['last_bytes_recieved'] = 0
        self.stats['check_interval'] = 2.0

        # Set up our socket and bind to our listen address and port.
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((listen_address, listen_port))

        # If this is a multicast receiver, set it up as such.
        if listen_type == "multicast":
            mreq = struct.pack(
                "4sl", socket.inet_aton(listen_address), socket.INADDR_ANY)
            self.sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Create a list of callbacks that we can schedule to run while we're
        # listening.
        self.scheduled_calls = []

        # If stats are enabled, start a recurring task that will calculate our
        # network stats every x seconds.
        if stats:
            self.call_later(self.stats['check_interval'],
                            self.calculate_stats, None)

    def listen(self):
        """Starts the listen loop. If threading is enabled, then the loop will
        be started in its own thread.

        Args:
          None

        Returns:
          None

        """

        self.listening = True
        if self.threading:
            from threading import Thread
            self.listen_thread = Thread(target=self.listen_loop)
            self.listen_thread.daemon = True
            self.listen_thread.start()

            self.scheduler_thread = Thread(target=self.scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()

        else:
            self.listen_loop()

    def listen_loop(self):
        """Starts the listen loop and executes the receieve_datagram method
        whenever a packet is receieved.

        Args:
          None

        Returns:
          None

        """

        while self.listening:
            try:
                data, address = self.sock.recvfrom(self.bufsize)
                self.receive_datagram(data, address)
                if self.stats_enabled:
                    self.stats['bytes_recieved'] += len(data)
            except socket.error as error:
                if error.errno == errno.WSAECONNRESET:
                    logger.info("connection reset")
                else:
                    raise

        logger.info("Shutting down the listener...")

    def scheduler(self, sleep_time=0.2):
        """Starts the scheduler to check for scheduled calls and execute them
        at the correct time.

        Args:
          sleep_time (float): The amount of time to wait in seconds between
            each loop iteration. This prevents the scheduler from consuming
            100% of the host's CPU. Defaults to 0.2 seconds.

        Returns:
          None

        """

        while self.listening:
            # If we have any scheduled calls, execute them and remove them from
            # our list of scheduled calls.
            if self.scheduled_calls:
                timestamp = time.time()
                self.scheduled_calls[:] = [item for item in self.scheduled_calls
                                           if not self.time_reached(timestamp, item)]
            time.sleep(sleep_time)

        logger.info("Shutting down the call scheduler...")

    def call_later(self, time_seconds, callback, arguments):
        """Schedules a function to be run x number of seconds from now.

        The call_later method is primarily used to resend messages if we
        haven't received a confirmation message from the receiving host.
        We can wait x number of seconds for a response and then try
        sending the message again.

        Args:
          time_seconds (float): The number of seconds from now we should call
            the provided function.
          callback (function): The method to execute when our time has been
            reached. E.g. self.retransmit
          arguments (dict): A dictionary of arguments to send to the callback.

        Returns:
          None

        """

        scheduled_call = {'ts': time.time() + time_seconds,
                          'callback': callback,
                          'args': arguments}
        self.scheduled_calls.append(scheduled_call)

    def time_reached(self, current_time, scheduled_call):
        """Checks to see if it's time to run a scheduled call or not.

        If it IS time to run a scheduled call, this function will execute the
        method associated with that call.

        Args:
          current_time (float): Current timestamp from time.time().
          scheduled_call (dict): A scheduled call dictionary that contains the
            timestamp to execute the call, the method to execute, and the
            arguments used to call the method.

        Returns:
          None

        Examples:

        >>> scheduled_call
        {'callback': <function foo at 0x7f022c42cf50>,
                 'args': {'k': 'v'},
                 'ts': 1415066599.769509}

        """

        if current_time >= scheduled_call['ts']:
            scheduled_call['callback'](scheduled_call['args'])
            return True
        else:
            return False

    def send_datagram(self, message, address, message_type="unicast"):
        """Sends a UDP datagram packet to the requested address.

        Datagrams can be sent as a "unicast", "multicast", or "broadcast"
        message. Unicast messages are messages that will be sent to a single
        host, multicast messages will be delivered to all hosts listening for
        multicast messages, and broadcast messages will be delivered to ALL
        hosts on the network.

        Args:
          message (str): The raw serialized packet data to send.
          address (tuple): The address and port of the destination to send the
            packet. E.g. (address, port)
          message_type -- The type of packet to send. Can be "unicast",
            "multicast", or "broadcast". Defaults to "unicast".

        Returns:
          None

        """

        if self.bufsize is not 0 and len(message) > self.bufsize:
            raise Exception("Datagram is too large. Messages should be " +
                            "under " + str(self.bufsize) + " bytes in size.")

        if message_type == "broadcast":
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        elif message_type == "multicast":
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        try:
            logger.debug("Sending packet")
            self.sock.sendto(message, address)
            if self.stats_enabled:
                self.stats['bytes_sent'] += len(message)
        except socket.error:
            logger.error("Failed to send, [Errno 101]: Network is unreachable.")

    def receive_datagram(self, data, address):
        """Executes when UDP data has been received and sends the packet data
        to our app to process the request.

        Args:
          data (str): The raw serialized packet data received.
          address (tuple): The address and port of the origin of the received
            packet. E.g. (address, port).

        Returns:
          None

        """

        # If we do not specify an application, just print the data.
        if not self.app:
            logger.debug("Packet received", address, data)
            return False

        # Send the data we've recieved from the network and send it
        # to our application for processing.
        try:
            response = self.app.handle_message(data, address)
        except Exception as err:
            logger.error("Error processing message from " + str(address) +
                          ":" + str(data))
            logger.error(traceback.format_exc())
            return False

        # If our application generated a response to this message,
        # send it to the original sender.
        if response:
            self.send_datagram(response, address)

    def calculate_stats(self, arguments):
        # Get our previous number of bytes sent.
        bytes_sent = self.stats['bytes_sent'] - self.stats['last_bytes_sent']
        bytes_recieved = self.stats['bytes_recieved'] - \
            self.stats['last_bytes_recieved']

        # Set our last number of bytes to the current one in preparation for
        # the next time this method is called.
        self.stats['last_bytes_sent'] = self.stats['bytes_sent']
        self.stats['last_bytes_recieved'] = self.stats['bytes_recieved']

        # Calculate the traffic in KiB/s.
        self.stats['kbps_sent'] = (float(bytes_sent) / 1024) / \
            self.stats['check_interval']
        self.stats['kbps_recieved'] = (float(bytes_recieved) / 1024) / \
            self.stats['check_interval']

        # Schedule this calculation to run again in x number of seconds.
        self.call_later(self.stats['check_interval'],
                        self.calculate_stats, None)

