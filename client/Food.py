import time
import math
import numpy as np
import pygame.draw

import Tanks
import drawing


class FoodSquare:
    def __init__(self):
        self.last_time = time.time()

        self.rotation = 0
        self.rotation_speed = 30  # x degree per second
        self.angle = 0  # in radians
        self.speed = 10

        self.pos = np.array([0, 0], dtype=np.float)
        self.radius = 0
        self.contour_thickness = 4

        self.basic_colors: np.array = None
        self.colors: np.array = None
        self.colors_hit_dif: np.array = np.empty((2, 4))

        self.is_disappearing = False
        self.is_hit = False
        self.animation_time = 2
        self.current_animation_time = 0.15

    def draw(self, surface):
        """
        :param surface: pygame surface to draw the projectile
        :return: True => object will no longer be rendered, must be removed from the list; False => just ignore this
        """

        if self.is_disappearing:
            if Tanks.process_disappear_animation(self):
                return True
        elif self.is_hit:
            Tanks.process_hit_animation(self)

        r2 = self.radius - 2 * self.contour_thickness
        s = drawing.get_surface((self.radius, self.radius))
        # pygame.draw.rect(s, (255, 0, 0, 30), s.get_rect())
        pygame.draw.rect(s, self.colors[1], [0, 0, self.radius, self.radius])
        pygame.draw.rect(s, self.colors[0], [self.contour_thickness, self.contour_thickness, r2, r2])
        drawing.rotate_surface_and_draw(surface, s, self.rotation, self.pos - drawing.drawing_offset)
        # print(self.pos)

    def set_hit_colors(self, color, contour_color):
        for i, color_ in enumerate(self.colors_hit_dif):
            self.colors_hit_dif[i] = color - self.basic_colors[i]

    def set_pos(self, x, y):
        self.pos[0], self.pos[1] = x, y

    def set_speed(self, speed: [float, int], angle: [float, int]):
        """
        :param speed: speed vector value
        :param angle: angle in degrees
        """
        self.speed = speed
        self.angle = angle / 180 * math.pi
