import asyncio
import traceback
import websockets
import sys

import processing
import settings

if sys.version_info[1] < 9:
    print("Python 3.9+ required!")
    exit(1)

processing = processing.Processing(60, settings.food_amount, settings.map_dim)
start_server = websockets.serve(processing.net.serve_connection, "", 2021)


async def multiple_tasks():
    input_coroutines = [start_server, processing.start(), processing.auto_spawn_food()]
    res = await asyncio.gather(*input_coroutines, return_exceptions=False)
    return res


if __name__ == '__main__':
    while True:
        try:
            res1, res2 = asyncio.get_event_loop().run_until_complete(multiple_tasks())
        except Exception as e:
            print("[__main__] main thread exception:", e)
            print(traceback.format_exc())
