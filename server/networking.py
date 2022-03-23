import json
import math
import traceback

import numpy as np

import tools
import settings


class Networking:
    def __init__(self, p):
        self.enable_traceback = False
        self.processing = p
        self.ws_conns = {}

    async def serve_connection(self, websocket, path):
        j = json.loads(await websocket.recv())

        uuid_ = await self.processing.spawn_tank(websocket, j["name"], 40)
        await websocket.send(json.dumps({"type": "uuid_change", "payload": {"uuid": uuid_}}))
        await websocket.send(json.dumps({"type": "items", "payload": self.processing.pack()}))
        tank = self.processing.tanks[uuid_]

        print("[serve_connection] new connection:", uuid_)
        try:
            while True:
                j = json.loads(await websocket.recv())
                if np.linalg.norm(np.array(j["pos"]) - np.array(tank["pos"])) > 200:
                    print(np.linalg.norm(np.array(j["pos"]) - np.array(tank["pos"])))
                    await websocket.send(json.dumps({"type": "force_position", "payload": tank["pos"]}))
                    j["pos"] = tank["pos"]

                if not tools.collide(j["pos"], (0, 0), self.processing.world_size):
                    await websocket.send(json.dumps({"type": "force_position", "payload": j["pos"]}))
                    j["pos"] = np.clip(j["pos"], 0, settings.map_dim).tolist()

                if j["shoot"]:
                    bullet_pos = [*j["pos"]]
                    bullet_pos[0] += math.sin(j["rotation"] * math.pi / 180) * -self.processing.tanks[uuid_]["radius"]
                    bullet_pos[1] += math.cos(j["rotation"] * math.pi / 180) * -self.processing.tanks[uuid_]["radius"]

                    await self.processing.spawn_projectile(
                        bullet_pos, j["rotation"], tank["bullet_speed"], tank["bullet_radius"], tank["bullet_damage"],
                        "projectile", "bullet", uuid_)

                if j["explode"]:
                    if self.processing.tanks[uuid_]["inventory"]["bombs"] > 0:
                        self.processing.tanks[uuid_]["inventory"]["bombs"] -= 1
                        await websocket.send(
                            json.dumps({"type": "inventory", "payload": self.processing.tanks[uuid_]["inventory"]}))
                        await self.processing.explode(self.processing.tanks[uuid_]["pos"], self.processing.tanks[uuid_])

                await self.processing.update_tank(uuid_, j["pos"], j["rotation"], j["current_shooting_time"])
        except Exception as e:
            print("[serve_connection] client exception in main thread:", e)
            if self.enable_traceback:
                print(traceback.format_exc())
        finally:
            try:
                await self.processing.delete_tank(uuid_, False)
            except Exception:
                pass

    async def notify_all(self, notification, *exclude_ids):
        notification_str = None
        if type(notification) == dict:
            if notification["type"] != "items" and notification["type"] != "all_items":
                notification_str = json.dumps(notification)

        for uuid_, ws in self.ws_conns.items():
            if uuid_ not in exclude_ids:
                try:
                    if notification_str is None:
                        notification_ = notification.copy()
                        items = {}
                        for a, b in notification_["payload"].items():
                            item_pos_to_tank = np.array(b["pos"]) - np.array(self.processing.tanks[uuid_]["pos"])
                            if tools.collide(item_pos_to_tank, -settings.display_window_size_half,
                                             settings.display_window_size_half):
                                items[a] = b
                        notification_["payload"] = items
                        await ws.send(json.dumps(notification_))
                    else:
                        await ws.send(notification_str)
                except Exception as e:
                    print("[notify_all] client exception:", uuid_, ": ", e)
                    if self.enable_traceback:
                        print(traceback.format_exc())

    async def notify_about_tank(self, type_, uuid_, notify_this=True):
        # must use None instead of False
        await self.notify_all({"type": type_,
                               "payload": {uuid_: self.processing.tanks[uuid_]}}, notify_this and uuid_)
