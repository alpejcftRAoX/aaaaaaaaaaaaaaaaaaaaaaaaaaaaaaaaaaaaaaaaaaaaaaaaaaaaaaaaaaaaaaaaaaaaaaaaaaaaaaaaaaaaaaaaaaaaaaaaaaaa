import asyncio
import math
import random
import time
import traceback
import uuid

import numpy as np

import networking
import tools
import settings

tank_colors = ([255, 232, 105, 255], [191, 174, 78, 255], [153, 153, 153, 255], [114, 114, 114, 255],
               [255, 255, 255, 255], [85, 85, 85, 255], [255, 255, 255, 255], [85, 85, 85, 255],
               [133, 227, 125, 255], [85, 85, 85, 255])
bullet_colors = ([0, 178, 225, 255], [0, 133, 168, 255])
food_colors = ([255, 232, 105, 255], [191, 174, 78, 255])


class Processing:
    def __init__(self, processing_rate, food_amount=300, map_dim=2000):
        self.enable_traceback = False

        self.processing_time = 1 / processing_rate
        self.tanks = {}
        self.food = {}
        self.projectiles = {}

        self.world_size = np.array([map_dim, map_dim])
        self.food_amount = food_amount

        self.net = networking.Networking(self)

    def pack(self):
        return self.tanks | self.food | self.projectiles

    async def spawn_food(self, pos, speed, radius, health, type_, class_):
        uuid_ = str(uuid.uuid4())
        self.food[uuid_] = {"uuid": uuid_, "type": type_, "class": class_, "pos": pos,
                            "angle": random.randint(1, 360),
                            "speed": speed, "rotation_speed": random.randint(5, 15) * random.choice([1, -1]),
                            "radius": radius, "health": health, "rotation": 0, "score": 10,
                            "colors": food_colors, "is_hit": False, "is_disappearing": False, "animation_time": .15,
                            "current_animation_time": 0, "lifetime": 10, "last_time": time.time()}

    async def spawn_projectile(self, pos, angle, speed, radius, health, type_, class_, parent):
        uuid_ = str(uuid.uuid4())
        self.projectiles[uuid_] = {"uuid": uuid_, "type": type_, "class": class_, "pos": pos, "angle": angle,
                                   "speed": speed,
                                   "radius": radius, "health": health, "colors": bullet_colors, "parent": parent,
                                   "is_disappearing": False, "disappearing_time": .1,
                                   "lifetime": settings.projectile_lifetime, "last_time": time.time()}
        await self.net.notify_all({"type": "items", "payload": {uuid_: self.projectiles[uuid_]}})

    async def spawn_tank(self, ws, name, health, pos=None):
        uuid_ = str(uuid.uuid4())
        self.tanks[uuid_] = {"uuid": uuid_, "type": "tank", "pos": pos or [random.randint(0, self.world_size[0]),
                                                                           random.randint(0, self.world_size[1])],
                             "colors": tank_colors, "rotation": 0, "current_shooting_time": 0, "score": 1000,

                             "health": health // 2, "regen_speed": 1, "name": name,
                             "max_health": health, "basic_max_health": health, "health_increase_health": 0.0015,

                             "bullet_damage": 2, "basic_bullet_damage": 2, "bullet_damage_increase_k": 0.001,
                             "bullet_speed": 180, "basic_bullet_speed": 180, "bullet_speed_increase_k": 0.002,
                             "bullet_radius": 10, "basic_bullet_radius": 10, "bullet_radius_increase_k": 0,

                             "tank_type": "default", "radius": 30, "is_hit": False, "is_disappearing": False,
                             "animation_time": .2, "current_animation_time": 0, "last_time": time.time(),
                             "last_damage_time": 0, "heal_after_damage_time": 10}
        await self.remove_food_around([*self.tanks[uuid_]["pos"], self.tanks[uuid_]["radius"] + 10])

        if ws is not None:
            self.net.ws_conns[uuid_] = ws
            await self.net.notify_about_tank("items", uuid_)
        return uuid_

    async def update_tank(self, uuid_, pos, rotation, notify_this=None):
        # notify_this: True -> this uuid will receive the notification; None -> this uuid will not receive it

        self.tanks[uuid_]["pos"] = pos
        self.tanks[uuid_]["rotation"] = rotation

        await self.net.notify_about_tank("items", uuid_, notify_this)

    async def delete_tank(self, uuid_, notify=False):
        del self.tanks[uuid_]
        del self.net.ws_conns[uuid_]
        if notify:
            await self.net.notify_all({"type": "delete", "payload": {uuid_: {"type": "tank"}}})

    async def process_items(self):
        while True:
            await asyncio.sleep(self.processing_time)
            t = time.time()

            items_to_remove = []

            # Movement
            for _, obj in self.projectiles.items():
                await self.move(obj, t - obj["last_time"])
            for _, obj in self.food.items():
                a = t - obj["last_time"]
                await self.move(obj, a)
                obj["rotation"] += obj["rotation_speed"] * a

            # Healing, updating tanks limits
            for t_uuid_, tank in self.tanks.items():
                # Gradually increasing max health level, bullet damage
                tank["max_health"] = tank["basic_max_health"] + tank["health_increase_health"] * tank["score"]
                tank["bullet_damage"] = tank["basic_bullet_damage"] + tank["bullet_damage_increase_k"] * tank["score"]
                tank["bullet_speed"] = tank["basic_bullet_speed"] + tank["bullet_speed_increase_k"] * tank["score"]
                tank["bullet_radius"] = tank["basic_bullet_radius"] + tank["bullet_radius_increase_k"] * tank["score"]

                if tank["is_disappearing"] or tank["health"] >= tank["max_health"] or tank["health"] == 0 or \
                        t - tank["last_damage_time"] < tank["heal_after_damage_time"]:
                    continue
                tank["health"] += tank["regen_speed"] * self.processing_time

            # Animation
            for uuid_, obj in (self.tanks | self.food).items():
                if obj["is_disappearing"]:
                    if obj["current_animation_time"] > obj["animation_time"]:
                        items_to_remove.append({"type": obj["type"], "uuid": uuid_})
                    else:
                        obj["current_animation_time"] += t - obj["last_time"]
                elif obj["is_hit"]:
                    if obj["current_animation_time"] > obj["animation_time"]:
                        obj["is_hit"] = False
                        obj["current_animation_time"] = 0
                    else:
                        obj["current_animation_time"] += t - obj["last_time"]
                obj["last_time"] = t
            for p_uuid_, projectile in self.projectiles.items():
                projectile["lifetime"] -= t - projectile["last_time"]
                projectile["last_time"] = t
                if projectile["lifetime"] < -projectile["disappearing_time"]:
                    items_to_remove.append({"type": "projectile", "uuid": p_uuid_})

            # Preventing food from 'leaving' game scene:
            for _, food in self.food.items():
                if food["pos"][0] < -20 or food["pos"][0] > self.world_size[0] + 20 or \
                        food["pos"][1] < -20 or food["pos"][1] > self.world_size[1] + 20:
                    await self.on_kill(food)

            # Projectiles hit detection
            p_keys = list(self.projectiles.keys())
            for i, p_uuid_ in enumerate(self.projectiles):
                projectile = self.projectiles[p_uuid_]
                # Preventing already disappearing projectile from being processed again
                if projectile["lifetime"] <= 0 or projectile["health"] == 0:
                    continue
                c1 = (*projectile["pos"], projectile["radius"])
                processed = False

                for i2 in range(i + 1, len(p_keys)):
                    projectile2 = self.projectiles[p_keys[i2]]
                    if projectile["parent"] != projectile2["parent"] and projectile2["health"] != 0:
                        if tools.are_intersecting(c1, (*projectile2["pos"], projectile["radius"])):
                            await self.hit(projectile, projectile2, t)
                            processed = True
                if processed:
                    continue

                for f_uuid_, obj in self.food.items():
                    if obj["is_disappearing"]:
                        continue
                    if tools.are_intersecting(c1, (*obj["pos"], obj["radius"])):
                        await self.hit(projectile, obj, t)
                        processed = True
                if processed:
                    continue

                for t_uuid_, tank in self.tanks.items():
                    if tank["is_disappearing"] or t_uuid_ == projectile["parent"] or tank["health"] == 0:
                        continue

                    if tools.are_intersecting(c1, (*tank["pos"], tank["radius"])):
                        await self.hit(projectile, tank, t)
                        processed = True
                if processed:
                    continue

            # Tanks hit detection
            t_keys = list(self.tanks.keys())
            for i, t_uuid_ in enumerate(self.tanks):
                tank = self.tanks[t_uuid_]
                processed = False
                for i2 in range(i + 1, len(t_keys)):
                    tank2 = self.tanks[t_keys[i2]]
                    if tools.are_intersecting((*tank["pos"], tank["radius"]), (*tank2["pos"], tank2["radius"])):
                        await self.hit(tank, tank2, t)
                        processed = True
                if processed:
                    break

                for f_uuid_, obj in self.food.items():
                    if obj["is_disappearing"]:
                        continue
                    if tools.are_intersecting((*tank["pos"], tank["radius"]), (*obj["pos"], obj["radius"])):
                        await self.hit(tank, obj, t)
                        processed = True
                if processed:
                    continue

            # Removing items
            await self.remove_obj(items_to_remove)
            # await self.disappear_obj(items_to_disappear)

            await self.net.notify_all({"type": "all_items", "payload": self.projectiles | self.tanks | self.food})

    async def move(self, obj, time_dif):
        obj["pos"][0] -= time_dif * obj["speed"] * math.sin(obj["angle"] / 180 * math.pi)
        obj["pos"][1] -= time_dif * obj["speed"] * math.cos(obj["angle"] / 180 * math.pi)

    async def disappear_obj(self, *items_to_disappear):
        for item in items_to_disappear:
            if item["type"] == "projectile":
                item["lifetime"] = 0 if item["lifetime"] > 0 else item["lifetime"]
            elif item["type"] == "food":
                if item["uuid"] in self.food:
                    item["is_disappearing"] = True
            elif item["type"] == "tank":
                if item["uuid"] in self.tanks:
                    item["is_disappearing"] = True

    async def remove_obj(self, items_to_remove):
        for item in items_to_remove:
            if item["type"] == "projectile":
                del self.projectiles[item["uuid"]]
            elif item["type"] == "food":
                del self.food[item["uuid"]]
            elif item["type"] == "tank":
                await self.delete_tank(item["uuid"])
        if len(items_to_remove) > 0:
            await self.net.notify_all(
                {"type": "delete", "payload": {a["uuid"]: {"type": a["type"]} for a in items_to_remove}})

    async def hit(self, obj1, obj2, t: time.time()):
        """
        :param t:
        Objects ex.: {type: "projectile/tank/food/...", uuid: "uuid_", health: 10}
        :param obj1: any object
        :param obj2: any object
        :return: None
        """

        if obj1["is_disappearing"] or obj2["is_disappearing"]:
            return

        if obj1["health"] == obj2["health"]:
            await self.on_kill(obj1, obj2)
            await self.on_kill(obj2, obj1)
        else:
            if obj1["health"] > obj2["health"]:
                obj_killer = obj1
                obj_killed = obj2
            else:
                obj_killer = obj2
                obj_killed = obj1

            obj_killer["health"] -= obj_killed["health"]
            obj_killer["current_animation_time"] = 0
            obj_killer["last_damage_time"] = t
            obj_killer["is_hit"] = True
            await self.on_kill(obj_killed, obj_killer)

    async def on_kill(self, obj_killed, obj_killer=None):
        if obj_killer is not None and "score" in obj_killed:
            if "parent" in obj_killer:
                t_uuid_ = obj_killer["parent"]
            elif obj_killer["type"] == "tank":
                t_uuid_ = obj_killer["uuid"]
            else:
                t_uuid_ = None
            if t_uuid_ is not None and t_uuid_ in self.tanks:
                self.tanks[t_uuid_]["score"] += obj_killed["score"]
        await self.disappear_obj(obj_killed)

    async def are_tanks_around(self, c2, radius_around):
        """
        :param radius_around: radius around the tank
        :param c2: [x, y, radius]
        :return:
        """

        for _, tank in self.tanks.items():
            if tools.are_intersecting((*tank["pos"], tank["radius"] + radius_around), c2):
                return True
        return False

    async def are_food_around(self, c2, radius_around):
        """
        :param radius_around:
        :param c2: [x, y, radius]
        :return:
        """

        for _, food in self.food.items():
            if tools.are_intersecting((*food["pos"], food["radius"] + radius_around), c2):
                return True
        return False

    async def remove_food_around(self, c1):
        """
        :param c1: [x, y, radius]
        :return:
        """

        for _, food in self.food.items():
            if tools.are_intersecting((*food["pos"], food["radius"]), c1):
                print("removing food to spawn:", food)
                await self.on_kill(food)

    async def auto_spawn_food(self):
        food_radius = settings.food_radius

        while True:
            try:
                to_spawn = self.food_amount - len(self.food)
                if len(self.food) == 0 or to_spawn / len(self.food) > 0.05:
                    print("[auto_spawn_food] Spawning food...")
                    for i in range(to_spawn):
                        success = False
                        while not success:
                            pos = [random.randint(0, self.world_size[0]), random.randint(0, self.world_size[1])]
                            if not await self.are_food_around([*pos, food_radius], 4)\
                                    and not await self.are_tanks_around([*pos, food_radius], 60):
                                await self.spawn_food(pos, random.randint(5, 10), food_radius, 4, "food", "square")
                                success = True
                    print("[auto_spawn_food] Spawn food complete")
            except Exception as e:
                print("[auto_spawn_food] error while spawning food:", e)
                if self.enable_traceback:
                    print(traceback.format_exc())
            await asyncio.sleep(5)

    async def start(self):
        await self.spawn_tank(None, "test", 20, [20, 20])
        while True:
            try:
                await self.process_items()
            except Exception as e:
                print("[start] error while processing items:", e)
                if self.enable_traceback:
                    print(traceback.format_exc())
