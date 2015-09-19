#!/usr/bin/python

from neteria.server import NeteriaServer
from example_middleware import ControllerMiddleware

import logging
import pygame
import sys

# Enable neteria logging to stdout for our server.
logger = logging.getLogger('neteria.server')
logger.setLevel(logging.DEBUG)
log_hdlr = logging.StreamHandler(sys.stdout)
log_hdlr.setLevel(logging.DEBUG)
logger.addHandler(log_hdlr)


class Game(object):

    def __init__(self):
        # Set up our middleware which will handle messages from the client.
        middleware = ControllerMiddleware(game_server=self)

        # Our "middleware" will populate this dictionary with legal directional
        # events from the client when they are received.
        self.network_events = {"left": False,
                               "right": False,
                               "up": False,
                               "down": False}

        # Create a Neteria server instance and start listening.
        self.server = NeteriaServer(middleware)
        self.server.listen()


        # Set up and configure PyGame.
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Neteria Server")
        self.clock = pygame.time.Clock()

        # Create a player sprite that we can move around.
        self.sprite = pygame.image.load("assets/player.png").convert_alpha()
        self.sprite_position = [(self.screen.get_width() / 2) - self.sprite.get_width() / 2,
                                (self.screen.get_height() / 2) - self.sprite.get_height() / 2]


    def start(self):
        # Set up our main game loop.
        while True:
            self.clock.tick(60)

            # Loop through all of our PyGame events.
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return

            if self.network_events["left"]:
                self.sprite_position[0] -= 1
            if self.network_events["right"]:
                self.sprite_position[0] += 1
            if self.network_events["up"]:
                self.sprite_position[1] -= 1
            if self.network_events["down"]:
                self.sprite_position[1] += 1

            self.screen.fill((0,0,0))
            self.screen.blit(self.sprite, self.sprite_position)

            if len(self.server.registry) > 0:
                pygame.display.set_caption("Neteria Server (Client Registered!)")

            pygame.display.flip()


mygame = Game()
mygame.start()
