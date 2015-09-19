from neteria.tools import _Middleware

class ControllerMiddleware(_Middleware):
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

