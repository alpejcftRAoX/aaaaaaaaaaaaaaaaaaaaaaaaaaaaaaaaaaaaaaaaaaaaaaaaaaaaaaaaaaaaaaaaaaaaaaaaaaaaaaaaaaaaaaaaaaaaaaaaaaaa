import json
import time

import numpy as np
import pygame

import drawing


def process_disappear_animation(ti):
    if ti.current_animation_time > ti.animation_time:
        return True

    k = ti.current_animation_time / ti.animation_time
    ti.radius *= 1 + k / 3
    for i, color in enumerate(ti.colors):
        ti.colors[i][3] *= 1 - k


def process_hit_animation(ti):
    k = ti.current_animation_time / ti.animation_time
    if k > 0.5:
        k = 1 - k

    if ti.current_animation_time > ti.animation_time:  # Finishing the animation
        ti.is_hit = False
        ti.current_animation_time = 0
    else:
        for i, color in enumerate(ti.colors_hit_dif):
            ti.colors[i] = np.clip(ti.basic_colors[i] + ti.colors_hit_dif[i] * k * 2, 0, 255)

        # ti.current_animation_time += time_dif


def reset_colors(ti):
    for i, color in enumerate(ti.colors):
        ti.colors[i] = np.copy(ti.basic_colors[i])


def set_colors(ti, *colors):
    ti.basic_colors = np.array(colors, dtype=np.float)
    reset_colors(ti)


def get_guns_offsets(ti, num_of_guns, time_dif):
    offsets = np.zeros(num_of_guns)
    if ti.current_shooting_time > ti.full_shooting_time:
        ti.current_shooting_time = 0
    else:
        if ti.current_shooting_time < ti.time_to_shoot:
            offsets[0] = 10 * ti.current_shooting_time / ti.time_to_shoot
        else:
            offsets[0] = 10 - 10 * (ti.current_shooting_time - ti.time_to_shoot) / ti.reload_time
        if ti.is_active:
            ti.current_shooting_time += time_dif
    return offsets


class TankDefault:
    def __init__(self, net):
        self.net = net

        self.is_active = False  # True - this is us
        self.name = "name"  # using color[]
        self.health = 0
        self.max_health = 0
        self.score = 0
        self.last_time = time.time()

        self.rotation = 0

        self.pos = np.array([0, 0], dtype=np.float)
        self.radius = 0
        self.contour_thickness = 4
        self.gun_rect = np.array([20, 40])

        # This tank will have 4 colors: 2 per body and 2 per gun
        # [0], [1] - body; [2], [3] - gun; [4], [5] - nickname; [6], [7] - score; [8], [9] - health bar
        self.basic_colors = np.empty((10, 4))
        self.colors = np.empty((10, 4))
        self.colors_hit_dif = np.empty((4, 4))

        self.is_disappearing = False
        self.is_hit = False
        self.animation_time = 2
        self.current_animation_time = 0

        self.is_shooting = False
        self.time_to_shoot = 0.1
        self.reload_time = 0.2
        self.full_shooting_time = self.time_to_shoot + self.reload_time
        self.current_shooting_time = 0
        self.shoot = False

        self.display_stats = True

    def pack(self):
        s = json.dumps({"pos": (self.pos).tolist(), "rotation": self.rotation,
                        "current_shooting_time": self.current_shooting_time, "shoot": self.shoot})
        if self.shoot:
            self.shoot = False
        return s

    def draw(self, surface):
        """
        :param surface: pygame surface to draw the projectile
        :return: True => object will no longer be rendered, must be removed from the list; False => just ignore this
        """

        t = time.time()
        a = t - self.last_time
        self.last_time = t

        if self.is_disappearing:
            if process_disappear_animation(self):
                return
        elif self.is_hit:
            process_hit_animation(self)

        gun_y_offset = 0
        if self.is_shooting or self.current_shooting_time != 0:
            if self.current_shooting_time == 0:
                self.shoot = True
            gun_y_offset = get_guns_offsets(self, 1, a)[0]
            if self.display_stats:
                self.net.send_tank_data = True

        b = 2 * (self.radius + max(self.gun_rect))
        s = drawing.get_surface((b, b))
        center = np.array((b // 2, b // 2))

        # Drawing gun
        gun_pos = np.array([center[0] - self.gun_rect[0] // 2, 20 + gun_y_offset])
        pygame.draw.rect(s, self.colors[3], (*gun_pos, *self.gun_rect))
        pygame.draw.rect(s, self.colors[2],
                         (*gun_pos + self.contour_thickness, *self.gun_rect - 2 * self.contour_thickness))
        # Drawing body
        # drawing.draw_circle_alpha(s, self.colors[1], center, self.radius)
        pygame.draw.circle(s, self.colors[1], center, self.radius)
        pygame.draw.circle(s, self.colors[0], center, self.radius - self.contour_thickness)

        drawing.rotate_surface_and_draw(surface, s, self.rotation, self.pos - drawing.drawing_offset)

        # Drawing stats
        if self.display_stats:
            drawing.draw_text_alpha(surface, self.pos + [0, -self.radius - 58] - drawing.drawing_offset, self.name,
                                    self.colors[4], self.colors[5], drawing.comic_sans_big)
            drawing.draw_text_alpha(surface, self.pos + [0, -self.radius - 40] - drawing.drawing_offset,
                                    self.format_score(), self.colors[6], self.colors[7], drawing.comic_sans_small)
            drawing.draw_progress_bar_alpha(surface, self.pos + [0, self.radius + 20] - drawing.drawing_offset,
                                            np.array([90, 13]), self.health / self.max_health, self.colors[9],
                                            self.colors[8])
        # print(self.pos)

    def set_hit_colors(self, color, contour_color):
        for i, color_ in enumerate(self.colors_hit_dif):
            self.colors_hit_dif[i] = color - self.basic_colors[i]

    def set_shooting_status(self, is_shooting: bool, current_shooting_time: float = None):
        self.is_shooting = is_shooting
        if current_shooting_time is not None:
            self.current_shooting_time = current_shooting_time

    def set_rotation(self, angle):
        self.rotation = angle

    def set_pos(self, x, y):
        self.pos = np.array([x, y], dtype=np.float)

    def add_to_pos(self, x, y):
        f = np.array([x, y], dtype=np.float)
        self.pos += f
        drawing.drawing_offset += f

    def format_score(self):
        return str(self.score) if self.score < 1000 else \
            "%.1fk" % (self.score / 1000) if self.score < 1000000 else "%.2fM" % (self.score / 1000000)
