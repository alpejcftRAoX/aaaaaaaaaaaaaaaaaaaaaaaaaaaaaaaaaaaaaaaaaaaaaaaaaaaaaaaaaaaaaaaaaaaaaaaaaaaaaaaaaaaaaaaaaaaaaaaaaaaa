import asyncio
import math
import os
import sys
import threading
import time

import numpy as np
import pygame

import drawing
import networking

if sys.version_info[1] < 9:
    print("Python 3.9+ required!")
    exit(1)

pygame.init()
print(f"Using {pygame.display.get_driver()}")


class Processing:
    def __init__(self):
        self.lastupdatetime = 0
        self.game = networking.GameDrawing(1920, 1080)
        self.loading_screen = networking.LoadingScreenDrawing(self.game)
        self.net = networking.Networking(self.game)

        self.our_speed = np.array([0, 0])
        self.velocity = 200
        self.max_speed = 200
        self.last_check = time.time()

    async def process_game(self, events):
        t = time.time()
        a = t - self.last_check
        self.last_check = t

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.game.our_tank.set_shooting_status(True)
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.game.our_tank.set_shooting_status(False)

        mouse_pos = np.array(pygame.mouse.get_pos()) * self.game.scaling_k
        rotation = math.atan2(*self.game.our_tank.pos - drawing.drawing_offset - mouse_pos) * 180 / math.pi
        if rotation != self.game.our_tank.rotation:
            self.game.our_tank.set_rotation(rotation)
            self.net.send_tank_data = True

        if not self.game.our_tank.is_active:
            self.our_speed = np.array([0, 0], dtype=float)

        cur_velocity = np.array([-self.our_speed[0], -self.our_speed[1]])
        keys = pygame.key.get_pressed()
        if keys[pygame.K_s]:
            cur_velocity[1] = self.velocity
        if keys[pygame.K_w]:
            cur_velocity[1] = -self.velocity
        if keys[pygame.K_a]:
            cur_velocity[0] = -self.velocity
        if keys[pygame.K_d]:
            cur_velocity[0] = self.velocity

        self.our_speed = np.clip(self.our_speed + cur_velocity * a, -self.max_speed, self.max_speed)
        self.game.our_tank.add_to_pos(*self.our_speed * a)
        if any(self.our_speed):
            pass
            self.net.send_tank_data = True
        if self.game.our_tank.is_shooting or self.game.our_tank.current_shooting_time > 0:
            self.net.send_tank_data = True

        self.game.draw_background(self.game.w, (0, 0))

        food = self.game.food.copy()
        tanks = self.game.tanks.copy()
        projectiles = self.game.projectiles.copy()

        # s = drawing.comic_sans_big.render(str(len(food) + len(tanks) + len(projectiles)), True, (255, 255, 0, 30))
        # self.game.w.blit(s, (0, 40))

        self.game.draw_fps(clock)
        self.game.draw_projectiles(projectiles)
        self.game.draw_food(food)
        self.game.draw_players(tanks)
        self.game.draw()

    async def process_loading_screen(self, events):
        self.game.our_tank.is_active = False
        res = self.loading_screen.draw(self.game.w, self.net.ws_status, events)
        if res["enter"]:
            self.connect(res["server"], res["nickname"])
        self.game.draw()

    def connect(self, uri, name):
        if self.net.ws_status not in ["WS_OPENING", "WS_OPENED"]:
            threading.Thread(target=self.net.run_forever, args=("ws://" + uri, name)).start()
        else:
            print("Wrong WS status:", self.net.ws_status)


processing = Processing()
threading.Thread(target=processing.net.sending_tank_data).start()

clock = pygame.time.Clock()

drawing.drawing_offset = -processing.game.center.astype(float)
processing.game.our_tank.is_shooting = False


async def main():
    run = True

    while run:
        clock.tick(60)
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.VIDEORESIZE:
                processing.game.resize(event.size)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False

            if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEBUTTONUP:
                event.pos = np.array(event.pos) * processing.game.scaling_k

        if processing.net.ws_status == "WS_OPENED":
            await processing.process_game(events)
        else:
            await processing.process_loading_screen(events)

    pygame.quit()
    os._exit(1)


asyncio.get_event_loop().run_until_complete(main())
