import time

import numpy as np
import pygame

pygame.font.init()
drawing_offset = np.array([0, 0], dtype=np.float)
comic_sans_big = pygame.font.SysFont("Comic Sans MS", 30)
comic_sans_small = pygame.font.SysFont("Comic Sans MS", 14)
comic_sans_med = pygame.font.SysFont("Comic Sans MS", 24)


def draw_circle_alpha(surface, color, center, radius):
    target_rect = pygame.Rect(center, (0, 0)).inflate((radius * 2, radius * 2))
    shape_surf = pygame.Surface(target_rect.size, pygame.SRCALPHA)
    pygame.draw.circle(shape_surf, color, (radius, radius), radius)
    surface.blit(shape_surf, target_rect)


def draw_rect_alpha(surface, color, rect, rot: int = None, center: tuple[int, int] = None):
    s = get_surface(rect)
    pygame.draw.rect(s, color, surface.get_rect())
    if rot is not None:
        s = pygame.transform.rotate(s, rot)
        rect = s.get_rect(center=center)
    surface.blit(s, rect)


def get_surface(size: [tuple[int, int], np.array]):
    return pygame.Surface(size, pygame.SRCALPHA)


def rotate_surface_and_draw(surface_master, surface, rot: int = 0,
                            rotation_point: (tuple[int, int], list[int, int]) = None):
    if rot != 0:
        surface = pygame.transform.rotate(surface, rot)
    surface_master.blit(surface, surface.get_rect(center=rotation_point))


def draw_text_alpha(surface, center: np.array, text, text_colour=(0, 0, 0, 0), shadow_colour=(0, 0, 0, 0),
                    font=comic_sans_big):
    rotate_surface_and_draw(surface, _draw_text_alpha(text, text_colour, shadow_colour, font),
                            rotation_point=center)


def _draw_text_alpha(text, text_colour=(0, 0, 0, 0), shadow_colour=(0, 0, 0, 0),
                     font=comic_sans_big):
    offset = np.array([1, 1])

    shadow = font.render(text, True, shadow_colour)
    text = font.render(text, True, text_colour)
    s = get_surface(text.get_rect().size + offset)
    s.blit(shadow, offset)
    s.blit(text, (0, 0))
    return s


def draw_progress_bar_alpha(surface, center: np.array, size: np.array, progress, empty_color=(0, 0, 0, 0),
                            fill_colour=(0, 0, 0, 0), contour_thickness=4):
    # progress - 0..1

    s = get_surface(size)
    pygame.draw.rect(s, empty_color, (0, 0, *size), border_radius=8)
    a = size - 2 * contour_thickness
    a[0] *= progress
    pygame.draw.rect(s, fill_colour, (contour_thickness, contour_thickness, *a), border_radius=8)

    rotate_surface_and_draw(surface, s, rotation_point=center)


class TextInput:
    def __init__(self, center: np.ndarray, size: np.ndarray, text="", label="", max_length=None, font=comic_sans_med):
        self.last_time = time.time()

        self.center = center
        self.rect = pygame.Rect(*(center - size // 2).tolist(), *size.tolist())

        self.basic_box_colors = np.array(((220, 220, 220, 255), (255, 255, 255, 255)))
        self.box_colors = self.basic_box_colors.copy()
        self.selected_box_colors = np.array(((200, 180, 255, 255), (255, 255, 255, 255)))
        self.selected_box_colors_dif = self.selected_box_colors - self.basic_box_colors

        self.animation_time = .15
        self.current_animation_time = self.animation_time

        self.min_size = size
        self.font = font
        self.text = text
        self.max_length = max_length
        self.label_surface = self.render_text(label)
        self.text_surface = self.render_text(self.text)
        self.active = False

    def render_text(self, text):
        return _draw_text_alpha(text, (43, 43, 43, 255), (119, 119, 119, 255), font=self.font)

    def handle_events(self, *events) -> str:
        """
        :param events: pygame events
        :return: text
        """

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    if not self.active:
                        self.current_animation_time = 0
                        self.active = True
                elif self.active:
                    self.current_animation_time = 0
                    self.active = False
            if event.type == pygame.KEYDOWN:
                if self.active:
                    if event.key == pygame.K_RETURN:
                        pass
                    elif event.key == pygame.K_BACKSPACE:
                        self.text = self.text[:-1]
                    elif event.key != pygame.K_ESCAPE and (self.max_length is None or len(self.text) < self.max_length):
                        self.text += event.unicode
                    self.text_surface = self.render_text(self.text)
        return self.text

    def draw(self, surface):
        self.rect.w = max(self.min_size[0], self.text_surface.get_width() + 10)

        t = time.time()
        if self.current_animation_time <= self.animation_time:
            a = self.current_animation_time / self.animation_time
            self.box_colors = self.basic_box_colors + self.selected_box_colors_dif * (a if self.active else 1 - a)
            self.current_animation_time += t - self.last_time
        else:
            self.box_colors = self.selected_box_colors.copy() if self.active else self.basic_box_colors.copy()
        self.last_time = t

        draw_progress_bar_alpha(surface, self.center, np.array(self.rect.size), 1, *self.box_colors,
                                contour_thickness=4)
        rotate_surface_and_draw(surface, self.text_surface, 0, self.center)
        surface.blit(self.label_surface, np.array(self.center) - [self.rect.w // 2,
                                                                  self.rect.h // 2 + self.label_surface.get_size()[
                                                                      1] + 4])
