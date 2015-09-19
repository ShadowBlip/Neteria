#!/usr/bin/python

import logging
import sys
import time
from neteria.server import NeteriaServer
from neteria.tools import _Middleware

# Create a middleware object that will echo events. "event_execute" is
# executed for every legal event message.
class EchoMiddleware(_Middleware):
    def event_legal(self, cuuid, euuid, event_data):
        return True

    def event_execute(self, cuuid, euuid, event_data):
        print event_data

# Create a client instance.
server = NeteriaServer(EchoMiddleware())
server.listen()
print "Server started. Press CTRL+C to quit."

while True:
    time.sleep(1)
