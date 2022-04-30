import asyncio
import json
import time

import numpy as np
import pygame
import websocket

import Food
import Projectiles
import Tanks
import drawing

our_uuid = ""


class GameDrawing:
    def __init__(self, w, h):
        self.win = pygame.display.set_mode((w, h),
                                           pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE | pygame.FULLSCREEN)
        w, h = 1920, 1080

        self.w = pygame.Surface([w, h])

        self.game_field = (32000, 32000)
        self.grid_cell = (20, 20)
        self.grid_thickness = 2
        self.grid_color = (195, 195, 195, 255)
        self.grid_precalculated = (set(), set())

        self.drawing_box = np.array([w, h])
        self.center = np.array((w // 2 if w % 2 == 0 else w // 2 + 1, h // 2 if h % 2 == 0 else h // 2 + 1))
        self.scaling_k = [1, 1]

        self.sync = asyncio.Lock()
        self.our_tank = Tanks.TankDefault(self)
        self.our_tank_uuid = ""
        self.tanks = {}
        self.food = {}
        self.projectiles = {}

        self.precalculate_grid()

    def precalculate_grid(self):
        self.grid_precalculated = (
            set(filter(lambda i: i % (self.grid_cell[0] + self.grid_thickness) >= self.grid_cell[0],
                       range(-self.center[0], self.game_field[0] + -self.center[0]))),
            set(filter(lambda i: i % (self.grid_cell[1] + self.grid_thickness) >= self.grid_cell[1],
                       range(-self.center[1], self.game_field[1] + self.center[1]))),
        )

    def draw(self):
        if self.w.get_size() != self.win.get_size():
            self.win.blit(pygame.transform.scale(self.w, self.win.get_size()), (0, 0))
        else:
            self.win.blit(self.w, (0, 0))
        pygame.display.flip()

    def draw_background(self, surface, p1: tuple[int, int]):
        """
        ! These are the in-game coordinates, not on-screen ones!
        :param surface: pygame surface
        :param p1: left top point; (x, y)
        # :param p2: right bottom point; (x, y)
        """
        p2 = p1 + self.drawing_box

        surface.fill((205, 205, 205, 255))

        v_offset = int(drawing.drawing_offset[0])
        for v in self.grid_precalculated[0].intersection(range(*np.array((p1[0], p2[0])) + v_offset)):
            pygame.draw.line(surface, self.grid_color, (v - v_offset, p1[1]), (v - v_offset, p2[1]))
        h_offset = int(drawing.drawing_offset[1])
        for h in self.grid_precalculated[1].intersection(range(*np.array((p1[1], p2[1])) + h_offset)):
            pygame.draw.line(surface, self.grid_color, (p1[0], h - h_offset), (p2[0], h - h_offset))

    def draw_fps(self, c: pygame.time.Clock):
        s = drawing.comic_sans_big.render(str(int(c.get_fps())), True, (0, 255, 0, 30))
        self.w.blit(s, (0, 0))

    def draw_inventory(self, inventory: dict):
        if "bombs" in inventory and inventory["bombs"] != 0:
            s = drawing.comic_sans_big.render(f"bombs: {inventory['bombs']}", True, (255, 30, 0, 30))
            self.w.blit(s, (10, self.w.get_size()[1] - s.get_size()[1]))

    def draw_players(self, players: dict):
        for uuid, player in players.items():
            # tank = None
            if uuid == self.our_tank_uuid:
                tank = self.our_tank
                if not tank.is_active:
                    tank.add_to_pos(*-(tank.pos - player["pos"]))
                    tank.is_active = True
            else:
                tank = Tanks.TankDefault(self)
                tank.pos = np.array(player["pos"])
                tank.rotation = player["rotation"]
                tank.current_shooting_time = player["current_shooting_time"]

            tank.colors = np.array(player["colors"])
            tank.basic_colors = np.array(player["colors"])
            tank.radius = player["radius"]
            tank.name = player["name"]
            # tank.name = player["uuid"]
            tank.score = player["score"]
            tank.health = player["health"]
            tank.max_health = player["max_health"]
            tank.inventory = player["inventory"]

            tank.is_disappearing = player["is_disappearing"]
            tank.is_hit = player["is_hit"]
            if tank.is_hit:
                tank.set_hit_colors((245, 135, 67, 255), (187, 108, 74, 255))

            tank.current_animation_time = player["current_animation_time"]
            tank.animation_time = player["animation_time"]

            # print(tank.name, tank.is_disappearing, tank.current_animation_time, tank.animation_time)

            tank.draw(self.w)

    def draw_projectiles(self, projectiles: dict):
        for uuid, projectile in projectiles.items():
            p = Projectiles.ProjectileBullet()
            p.colors = np.array(projectile["colors"])
            p.pos = np.array(projectile["pos"])
            p.angle = projectile["angle"]
            p.speed = projectile["speed"]
            p.radius = projectile["radius"]
            p.lifetime = projectile["lifetime"]
            p.disappear_time = projectile["disappearing_time"]

            p.draw(self.w)

    def draw_food(self, food: dict):
        for uuid, food in food.items():
            i = Food.FoodSquare()
            i.basic_colors = np.array(food["colors"])
            i.colors = i.basic_colors.copy()
            i.pos = np.array(food["pos"])
            i.radius = food["radius"]
            i.rotation = food["rotation"]

            i.is_disappearing = food["is_disappearing"]
            i.is_hit = food["is_hit"]
            if i.is_hit:
                i.set_hit_colors((245, 135, 67, 255), (187, 108, 74, 255))
            i.animation_time = food["animation_time"]
            i.current_animation_time = food["current_animation_time"]

            i.draw(self.w)

    def resize(self, size):
        # print("on resize")
        self.win = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE)
        # self.w = pygame.Surface([size[0], size[1]])
        # self.drawing_box = np.array([size[0], size[1]])
        self.scaling_k = np.array(self.w.get_size()) / np.array(self.win.get_size())
        # self.scaling_k = np.array((0.1, 0.1))
        print(self.scaling_k)


class LoadingScreenDrawing:
    def __init__(self, game_drawing: GameDrawing):
        self.background: pygame.Surface = drawing.get_surface((1920, 1080))
        self.game = game_drawing

        self.inputs: dict[str: drawing.TextInput] = \
            {"nickname": drawing.TextInput(self.game.center - [0, 40], np.array([300, 42]), label="Nickname (max 16):",
                                           max_length=16),
             "server": drawing.TextInput(self.game.center + [0, 40], np.array([300, 42]), text="127.0.0.1:2022",
                                         label="Server (ip:port):", max_length=21)}

        # Generating background image
        self.draw_background()

        self.bullet1 = Projectiles.ProjectileBullet()
        self.bullet1.pos = np.array((1467, 120))
        self.bullet1.radius = 10
        self.bullet1.colors = np.array(([0, 178, 225, 255], [0, 133, 168, 255]))

    def draw_food(self, surface, pos_on_screen, radius, rotation, disappearing_time):
        food = Food.FoodSquare()
        food.pos = np.array(pos_on_screen)
        food.radius = radius

        food.is_disappearing = disappearing_time > 0
        food.animation_time = 1
        food.current_animation_time = disappearing_time
        food.rotation = rotation

        food.colors = np.array(([255, 232, 105, 255], [191, 174, 78, 255]))
        food.draw(surface)

    def draw_bullet(self, surface, pos_on_screen, radius, disappearing_time):
        bullet = Projectiles.ProjectileBullet()
        bullet.pos = np.array(pos_on_screen)
        bullet.radius = radius
        bullet.disappear_time = 1
        bullet.lifetime = -disappearing_time
        bullet.colors = np.array(([0, 178, 225, 255], [0, 133, 168, 255]))
        bullet.draw(surface)

    def draw_tank(self, surface, pos_on_screen, rotation, radius, shooting_time):
        tank = Tanks.TankDefault(None)
        tank.colors = np.array(([255, 232, 105, 255], [191, 174, 78, 255], [153, 153, 153, 255], [114, 114, 114, 255],
                                [255, 255, 255, 255], [85, 85, 85, 255], [255, 255, 255, 255], [85, 85, 85, 255],
                                [133, 227, 125, 255], [85, 85, 85, 255]))
        tank.rotation = rotation
        tank.current_shooting_time = shooting_time
        tank.radius = radius
        tank.display_stats = False
        tank.set_pos(pos_on_screen[0] + drawing.drawing_offset[0], pos_on_screen[1] + drawing.drawing_offset[1])
        tank.draw(surface)

    def draw_background(self):
        self.game.draw_background(self.background, (0, 0))

        for i in range(10):
            self.draw_food(self.background, np.random.rand(2) * self.game.w.get_size(), 20, 20, 0)

        # self.draw_bullet(self.background, (1511, 132), 10, 0)
        self.draw_bullet(self.background, (1472, 133), 10, 0)
        self.draw_bullet(self.background, (1443, 136), 10, 0)
        self.draw_bullet(self.background, (1382, 114), 10, 0)
        self.draw_bullet(self.background, (1289, 90), 10, 0)

        self.draw_bullet(self.background, (1226, 702), 10, 0.9)
        self.draw_bullet(self.background, (1235, 751), 10, 0.5)
        self.draw_bullet(self.background, (1244, 792), 10, 0)
        self.draw_bullet(self.background, (1250, 847), 10, 0)
        self.draw_bullet(self.background, (1268, 902), 10, 0)
        self.draw_bullet(self.background, (1274, 958), 10, 0)
        self.draw_bullet(self.background, (1290, 1016), 10, 0.8)

        self.draw_bullet(self.background, (1324, 998), 10, 0)
        self.draw_bullet(self.background, (1279, 1020), 10, 0.8)

        self.draw_tank(self.background, (300, 700), 30, 40, 0)
        self.draw_tank(self.background, (1530, 100), 120, 30, 0.1)

    def draw(self, s: pygame.surface, ws_status, events):
        s.blit(self.background, (0, 0))

        if ws_status != "WS_OPENING":
            enter = False
            text_responses = {}
            for event in events:
                enter = enter or event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN
                text_responses = {a[0]: a[1].handle_events(event) for a in self.inputs.items()}
            for _, b in self.inputs.items():
                b.draw(s)

            drawing.draw_text_alpha(s, self.game.center-[0, 150], "Press 'Enter' to play, 'ESC' to exit", (0, 0, 0, 100), (255, 255, 255, 255), drawing.comic_sans_med)
            f = drawing.comic_sans_small.render("ws status: " + ws_status, True, (255, 0, 0))
            s.blit(f, (0, self.game.w.get_rect().h - f.get_rect().h))
            return {**text_responses, "enter": enter}
        else:
            drawing.draw_text_alpha(s, self.game.center-[0, 0], "Connecting...", (0, 0, 0, 100), (255, 255, 255, 255),
                                    drawing.comic_sans_big)
            return {"nickname": "", "server": "", "enter": False}


class Networking:
    def __init__(self, game: GameDrawing):
        self.our_name = ""
        self.send_tank_data = False
        self.game = game

        self.ws_status = "WS_NOT_INITIALIZED"
        # websocket.enableTrace(True)
        self.ws: websocket.WebSocketApp = websocket.WebSocketApp("")

    def run_forever(self, uri, name):
        self.our_name = name
        self.ws_status = "WS_OPENING"
        self.ws = websocket.WebSocketApp(uri,
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.ws.run_forever()
        print("run_forever_finished")
        self.ws_status = "WS_CLOSED"
        self.game.our_tank.is_active = False

    def send_message(self, msg):
        if self.ws_status != "WS_OPENED":
            return

        if type(msg) == dict:
            msg = json.dumps(msg)
        self.ws.send(msg)

    def sending_tank_data(self):
        while True:
            if self.ws_status == "WS_OPENED" and self.send_tank_data and self.game.our_tank.is_active:
                self.ws.send(self.game.our_tank.pack())
                self.send_tank_data = False
            time.sleep(0.02)

    def on_message(self, ws, message):
        j = json.loads(message)

        if j["type"] == "uuid_change":
            self.game.our_tank_uuid = j["payload"]["uuid"]
        elif j["type"] == "delete":
            pass  # no need to handle as server sends us all items every server tick
            # for uuid, a in j["payload"].items():
            #     continue
            #     if a["type"] == "tank":
            #         del self.game.tanks[uuid]
            #     elif a["type"] == "food":
            #         del self.game.food[uuid]
            #     elif a["type"] == "projectile":
            #         del self.game.projectiles[uuid]
        elif j["type"] == "items" or j["type"] == "all_items":
            tanks = {}
            food = {}
            projectiles = {}

            for uuid, item in j["payload"].items():
                if item["type"] == "tank":
                    tanks[uuid] = item
                elif item["type"] == "food":
                    food[uuid] = item
                elif item["type"] == "projectile":
                    projectiles[uuid] = item

            if j["type"] == "all_items":
                self.game.tanks = tanks
                self.game.food = food
                self.game.projectiles = projectiles
            else:
                self.game.tanks |= tanks
                self.game.food |= food
                self.game.projectiles |= projectiles
        elif j["type"] == "force_position":
            self.game.tanks[self.game.our_tank_uuid]["pos"] = j["payload"]
            self.game.our_tank.is_active = False
        elif j["type"] == "inventory":
            self.game.our_tank.inventory = j["payload"]

    def on_error(self, ws, error):
        self.ws_status = "WS_ERROR"
        print("on_error:", error)

    def on_close(self, ws):
        self.ws_status = "WS_CLOSED"

    def on_open(self, ws):
        self.ws_status = "WS_OPENED"
        self.send_message(json.dumps({"name": self.our_name}))
