#!/usr/bin/python
"""This module contains prototype middleware classes that you can use with your
Neteria server. Every Neteria server instance requires a middleware that will
process and handle events from the client. The middleware is also responsible
for determining if an event recieved from a client is legal or not."""

class _Middleware(object):

    """This is a prototype class for your server's middleware. Your
    middleware should inherit from it. No direct instances of this class
    should be created. The "event_legal" and "event_execute" methods MUST be
    overridden in the child class.

    The middleware is used to handle and process all events that come in from
    the clients. Since Neteria inheritely does not trust the client, ALL events
    that are recieved are passed through the "event_legal" method. If
    "event_legal" returns True, then it will pass to the "event_execute"
    method to process the event. If "event_legal" returns False, then it will
    not be executed and the client will recieve a response indicating that
    the event was ILLEGAL.

    Args:
      game_server (object): An instance of the application that is running the
        Neteria server.

    """

    def __init__(self, game_server=None):
        self.game_server = game_server
        self.server = None

    def event_legal(self, cuuid, euuid, event_data):
        """Determines whether or not the event is LEGAL or ILLEGAL. If the
        event is LEGAL, the Neteria server will execute the "event_execute"
        method. This method should be overridden in the child class, otherwise
        ALL events from the client will be considered LEGAL.

        Args:
          cuuid (string): The client's universally unique identifier (uuid).
          euuid (string): The event's universally unique identifier (uuid).
          event_data (any): Arbitrary data sent from the client.

        Returns:
          True if the event is LEGAL. False if the event was ILLEGAL.

        """
        return True

    def event_execute(self, cuuid, euuid, event_data):
        """If the event was LEGAL, execute the event on the server. This method
        MUST be overridden in the child class. Otherwise this method does
        nothing.

        Args:
          cuuid (string): The client's universally unique identifier (uuid).
          euuid (string): The event's universally unique identifier (uuid).
          event_data (any): Arbitrary data sent from the client.

        Returns:
          None

        """
        pass


class _ControllerMiddleware(_Middleware):

    """This middleware will allow you to use the NeteriaServer as a basic
    controller. When it receives KEYDOWN/KEYUP events, it will set the
    corresponding dictionary key in "network_events" to true or false. In your
    main game loop, you can then iterate through this dictionary and change
    the game accordingly.

    """

    def __init__(self, game_server=None):
        _Middleware.__init__(self, game_server)

    def event_execute(self, cuuid, euuid, event_data):
        if event_data == "KEYDOWN:down":
            self.game_server.network_events["down"] = True
        elif event_data == "KEYUP:down":
            self.game_server.network_events["down"] = False
        elif event_data == "KEYDOWN:up":
            self.game_server.network_events["up"] = True
        elif event_data == "KEYUP:up":
            self.game_server.network_events["up"] = False
        elif event_data == "KEYDOWN:left":
            self.game_server.network_events["left"] = True
        elif event_data == "KEYUP:left":
            self.game_server.network_events["left"] = False
        elif event_data == "KEYDOWN:right":
            self.game_server.network_events["right"] = True
        elif event_data == "KEYUP:right":
            self.game_server.network_events["right"] = False
