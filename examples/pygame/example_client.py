#!/usr/bin/python
"""This example demonstrates using the Neteria client to connect to a Neteria
server to act as a game controller using PyGame.

You can run this example with the following command:

python ./example_client.py
"""

from neteria.client import NeteriaClient
import logging
import pygame

# Enable logging to stdout for our client.
import sys
logger = logging.getLogger('neteria.client')
logger.setLevel(logging.DEBUG)
log_hdlr = logging.StreamHandler(sys.stdout)
log_hdlr.setLevel(logging.DEBUG)
logger.addHandler(log_hdlr)


class Game(object):

    def __init__(self):

        # Set up our Neteria client.
        self.client = NeteriaClient()
        self.client.listen()


        # Set up and configure PyGame.
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        self.clock = pygame.time.Clock()
        font = pygame.font.Font(None, 36)
        self.text = font.render("Press ENTER to auto-register.", 1, (240, 240, 240))
        pygame.display.set_caption("Neteria Client (Not connected)")


        # Create a game pad that we will use to control the player on the
        # server.
        ######## UP Arrow ########
        self.up_arrow = pygame.image.load(
            "assets/client-up.png").convert_alpha()
        self.up_arrow_pos = (
            (self.screen.get_width() / 2) - (self.up_arrow.get_width() / 2),
            (self.screen.get_height() / 2) - self.up_arrow.get_height())
        self.up_arrow_rect = pygame.Rect(self.up_arrow_pos,
                                         self.up_arrow.get_size())

        ######## DOWN Arrow ########
        self.down_arrow = pygame.image.load(
            "assets/client-down.png").convert_alpha()
        self.down_arrow_pos = (
            (self.screen.get_width() / 2) - (self.down_arrow.get_width() / 2),
            (self.screen.get_height() / 2))
        self.down_arrow_rect = pygame.Rect(self.down_arrow_pos,
                                           self.down_arrow.get_size())

        ######## LEFT Arrow ########
        self.left_arrow = pygame.image.load(
            "assets/client-left.png").convert_alpha()
        self.left_arrow_pos = (
            (self.screen.get_width() / 2) - self.left_arrow.get_width(),
            (self.screen.get_height() / 2) - self.left_arrow.get_height() / 2)
        self.left_arrow_rect = pygame.Rect(self.left_arrow_pos,
                                           self.left_arrow.get_size())

        ######## RIGHT Arrow ########
        self.right_arrow = pygame.image.load(
            "assets/client-right.png").convert_alpha()
        self.right_arrow_pos = (
            (self.screen.get_width() / 2),
            (self.screen.get_height() / 2) - self.right_arrow.get_height() / 2)
        self.right_arrow_rect = pygame.Rect(self.right_arrow_pos,
                                            self.right_arrow.get_size())


    def start(self):
        # Set up our main game loop.
        while True:
            self.clock.tick(60)
            self.screen.fill((0,0,0))
            self.screen.blit(self.text, (0, 0))

            # Draw the arrows on the screen.
            self.screen.blit(self.up_arrow, self.up_arrow_pos)
            self.screen.blit(self.down_arrow, self.down_arrow_pos)
            self.screen.blit(self.left_arrow, self.left_arrow_pos)
            self.screen.blit(self.right_arrow, self.right_arrow_pos)


            # Loop through all of our PyGame events.
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self.client.autodiscover(autoregister=True)

                # If we clicked on our directional pad, send an event to the server.
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_position = pygame.mouse.get_pos()
                    if self.up_arrow_rect.collidepoint(mouse_position):
                        self.client.event("KEYDOWN:up")
                    if self.down_arrow_rect.collidepoint(mouse_position):
                        self.client.event("KEYDOWN:down")
                    if self.left_arrow_rect.collidepoint(mouse_position):
                        self.client.event("KEYDOWN:left")
                    if self.right_arrow_rect.collidepoint(mouse_position):
                        self.client.event("KEYDOWN:right")

                # When we release the mouse, send a key up event.
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.client.event("KEYUP:up")
                    self.client.event("KEYUP:down")
                    self.client.event("KEYUP:left")
                    self.client.event("KEYUP:right")

            # If the client successfully registers, change the window title.
            if self.client.registered:
                pygame.display.set_caption("Neteria Client (Registered!)")

            pygame.display.flip()


mygame = Game()
mygame.start()
