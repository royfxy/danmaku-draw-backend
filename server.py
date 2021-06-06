from math import exp
from os import execlpe
from sanic import Sanic
from sanic.response import json, text
from sanic_token_auth import SanicTokenAuth

from websocket_sender import WebsocketSender, Message, MessageType
from music import Playlist, MusicService
from canvas import Canvas
from live_handler import DanmakuClient, LiveHandler

import random
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

app = Sanic("bilibili_danmu_draw")

chars = "ZYXWUVTSRQPONMLKJIHGFEDCBAzyxwvutsrqponmlkjihgfedcba0987654321"
secret_key = "".join(random.sample(chars,16))
auth = SanicTokenAuth(app,
                      secret_key=secret_key,
                      header='XAuth-Token')

print(f"SECRET KEY: {secret_key}")



music_service = MusicService(3000, "localhost")
Playlist.set_serivce(music_service)

message_sender = WebsocketSender(3001, "localhost")
canvas_sender = WebsocketSender(3002, "localhost")

live_handler = LiveHandler(message_sender=message_sender,
                           canvas_sender=canvas_sender)
client = DanmakuClient(os.getenv("LIVE_ID"), handler=live_handler)


# @atexit.register
# def shutdown():
#     logging.debug(f"Shuting Down.")
#     # loop = asyncio.get_event_loop().create_task(live_handler.store_all)
#     live_handler.store_all()
#     # loop

@app.get("/api/music/playlist")
@auth.auth_required
async def get_playlist(request):
    return json(Playlist.playlist().to_json())

@app.get("/api/music/play")
@auth.auth_required
async def music_detail(request):
    return json((await Playlist.play()).to_json())

@app.get("/api/music/skip")
@auth.auth_required
async def skip_song(request):
    if Playlist.skip():
        return json(Playlist.playlist().to_json())

@app.get("/api/canvas/canvas")
async def get_canvas(request):
    return json(Canvas.canvas().to_json())

@app.get("/api/exit")
async def exit_backend(request):
    live_handler.store_all()
    # sys.exit()
    return text("OK")

# app.run(host="127.0.0.1", port=3003, auto_reload=False)


server = app.create_server(host="127.0.0.1", port=3003, return_asyncio_server=True)
asyncio.get_event_loop().create_task(server)
asyncio.get_event_loop().run_forever()
