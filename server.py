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
live_room_logger = logging.getLogger("live_room")
live_room_logger.setLevel(logging.INFO)
live_room_logger_handler = logging.FileHandler(
    filename="live-room.log", mode="w")
live_room_logger_handler.setLevel(logging.INFO)
live_room_logger_formatter = logging.Formatter(
    '%(asctime)s: %(levelname)s - %(message)s')
live_room_logger_handler.setFormatter(live_room_logger_formatter)
live_room_logger.addHandler(live_room_logger_handler)

logging_level = getattr(logging, args["log"].upper(), None)
if not isinstance(logging_level, int):
    logging_level = 30
print(logging_level)
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
                             config_music["ip"],
                             config_music["cookie"])
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

client = DanmakuClient(config_live["id"], handler=live_handler,
                       logger=live_room_logger)


@sanic_app.get("/api/message/hints")
async def get_hints(request):
    return sjson(live_handler.get_init_message().to_json())


@sanic_app.get("/api/music/playlist")
@auth.auth_required
async def get_playlist(request):
    return sjson((await Playlist.playlist()).to_json())


@sanic_app.get("/api/music/playlist/default")
@auth.auth_required
async def get_playlist(request):
    return sjson(Playlist.default_palylist())


@sanic_app.get("/api/music/play")
@auth.auth_required
async def music_detail(request):
    succeed, play_message = await Playlist.play()
    if not succeed:
        await Playlist.skip()
        await message_sender.send(await Playlist.playlist())
    return sjson(play_message.to_json())


@sanic_app.get("/api/music/skip")
@auth.auth_required
async def skip_song(request):
    await Playlist.skip()
    await message_sender.send(await Playlist.playlist())
    return sjson((await Playlist.playlist()).to_json())


@sanic_app.post("/api/music/add")
@auth.auth_required
async def add_default_song(request):
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


@sanic_app.post("/api/user/changeweight")
@auth.auth_required
async def add_default_song(request):
    request_json = request.json
    print(request_json)
    if "weight" in request_json and "uid" in request_json:
        try:
            weight_value = int(request_json["weight"])
            await live_handler.change_weight(request_json["uid"],
                                         weight_value)
            return text("OK")
        except Exception:
            pass
    return text("Error")

server = sanic_app.create_server(access_log=False,
                                 host=config_sanic["ip"],
                                 port=config_sanic["port"],
                                 return_asyncio_server=True)
asyncio.get_event_loop().create_task(server)
asyncio.get_event_loop().run_forever()
