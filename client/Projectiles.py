import time
import math

import numpy as np
import pygame

import drawing


class ProjectileBullet:
    def __init__(self):
        self.last_time = time.time()
        self.lifetime = 5
        self.disappear_time = 0.1

        self.rotation = 0
        self.rotation_speed = 30

        self.pos = np.array([0, 0], dtype=np.float)
        self.angle = 0
        self.speed = 0
        self.radius = 0
        self.contour_thickness = 4
        self.colors = np.array([[0, 133, 168, 255], [0, 178, 225, 255]])

    def draw(self, surface: pygame.Surface):
        if self.lifetime < -self.disappear_time:
            return True

        if self.lifetime <= 0:
            k = 1 - abs(self.lifetime) / self.disappear_time
            self.radius += 3 * (1 - k)
            self.colors[0][3] *= k
            self.colors[1][3] *= k

        drawing.draw_circle_alpha(surface, self.colors[1], self.pos - drawing.drawing_offset, self.radius)
        drawing.draw_circle_alpha(surface, self.colors[0], self.pos - drawing.drawing_offset,
                                  self.radius - self.contour_thickness)

    def set_pos(self, x, y):
        self.pos = np.array([x, y], dtype=np.float)
