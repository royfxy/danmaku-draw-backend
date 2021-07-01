import argparse
import asyncio
import logging
import random
import json

from sanic import Sanic
from sanic.response import text
from sanic.response import json as sjson
from sanic_token_auth import SanicTokenAuth

from canvas import Canvas
from live_handler import DanmakuClient, LiveHandler
from music import Playlist, MusicService
from sql import SQL
from websocket_sender import WebsocketSender

# Reading configurations from config.json
with open("./config.json", "r") as json_file:
    config = json.load(json_file)
config_db = config["database"]
config_live = config["liveroom"]
config_music = config["music"]
config_canvas = config["canvas"]
config_messagews = config["messagews"]
config_sanic = config["sanic"]
config_initmessage = config["initmessage"]

# Parse arguements
parser = argparse.ArgumentParser()
parser.add_argument('--log', default="warning")
parser.add_argument('--token', default=None)
args = vars(parser.parse_args())

# Config logging
logging_level = getattr(logging, args["log"].upper(), None)
if not isinstance(logging_level, int):
    logging_level = 30
logging.basicConfig(filename='./server.log', filemode='w', level=logging_level)

# Connect to SQL
sql = SQL()
sql.connect(host=config_db["host"], port=config_db['port'], db=config_db["db"],
            username=config_db["username"], password=config_db["password"])

sanic_app = Sanic("danmaku_draw_game")

# Auth token
secret_key = args["token"]
if not secret_key:
    chars = "ZYXWUVTSRQPONMLKJIHGFEDCBAzyxwvutsrqponmlkjihgfedcba0987654321"
    secret_key = "".join(random.sample(chars, 16))
auth = SanicTokenAuth(sanic_app,
                      secret_key=secret_key,
                      header='XAuth-Token')

print(f"SECRET KEY: {secret_key}")

# Config canvas
Canvas.config(col=config_canvas["col"], row=config_canvas["row"])

# Config music
music_service = MusicService(config_music["port"],
                             config_music["ip"])
Playlist.set_serivce(music_service)
if "default" in config_music:
    for query in config_music["default"]:
        Playlist.add_to_default(query)

message_sender = WebsocketSender(config_messagews["port"],
                                 config_messagews["ip"],)
canvas_sender = WebsocketSender(config_canvas["port"],
                                config_canvas["ip"],)

live_handler = LiveHandler(message_sender=message_sender,
                           canvas_sender=canvas_sender,
                           init_message=config_initmessage)

client = DanmakuClient(config_live["id"], handler=live_handler)


@sanic_app.get("/api/message/hints")
async def get_hints(request):
    return sjson(live_handler.get_init_message().to_json())


@sanic_app.get("/api/music/playlist")
@auth.auth_required
async def get_playlist(request):
    return sjson((await Playlist.playlist()).to_json())


@sanic_app.get("/api/music/play")
@auth.auth_required
async def music_detail(request):
    return sjson((await Playlist.play()).to_json())


@sanic_app.get("/api/music/skip")
@auth.auth_required
async def skip_song(request):
    await Playlist.skip()
    return sjson((await Playlist.playlist()).to_json())

@sanic_app.post("/api/music/add")
@auth.auth_required
async def add_default_song(request):
    print(request.json)
    if "query" in request.json:
        Playlist.add_to_default(request.json["query"])
        return text("OK")
    return text("Error")

@sanic_app.get("/api/canvas/canvas")
async def get_canvas(request):
    return sjson(Canvas.canvas().to_json())


@sanic_app.post("/api/exit")
async def exit_backend(request):
    live_handler.store_all()
    return text("OK")

server = sanic_app.create_server(host=config_sanic["ip"],
                                 port=config_sanic["port"],
                                 return_asyncio_server=True)
asyncio.get_event_loop().create_task(server)
asyncio.get_event_loop().run_forever()
