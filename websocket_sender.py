import asyncio
import websockets
import threading
import json
from enum import Enum, unique

import logging

logging.basicConfig(level=logging.DEBUG)

@unique
class MessageType(Enum):
    DRAW_PIXEL = 0
    DRAW_SUBPIXEL = 1
    TEXT_MESSAGE = 2
    UPDATE_PLAYLIST = 3
    PLAY_SONG = 4
    SKIP_SONG = 5
    INIT_CANVAS = 6
    NONE = 7


class Message:
    def __init__(self, message_type: MessageType, data):
        self._type = message_type
        self._data = data

    @classmethod
    def none(cls):
        return Message(MessageType.NONE, None)

    def to_json(self):
        return {"type": self._type.name, "data": self._data}

    def __str__(self):
        return json.dumps(self.to_json())


class WebsocketSender:
    def __init__(self, port, ip = 'localhost'):
        self._port = port
        self._ip = ip
        self._loop = asyncio.new_event_loop()
        self._future = None
        self._websocket = set()
        self._start(self._loop)
        
    def _start(self, loop):
        def run_forever(loop):
            asyncio.set_event_loop(loop)
            asyncio.ensure_future(websockets.serve(self._connect, self._ip, self._port))
            loop.run_forever()
        
        thread = threading.Thread(target=run_forever, args=(loop,))
        thread.daemon=True
        thread.start()

    async def _connect(self, websocket, path):
        self._websocket.add(websocket)
        while True:
            self._future = self._loop.create_future()
            message = await self._future
            count = 0
            for ws in list(self._websocket):
                try:
                    await ws.send(str(message))
                    count += 1
                except websockets.exceptions.ConnectionClosed:
                    self._websocket.remove(ws)
                except TypeError:
                    pass
            logging.debug(f"Sent message \"{str(message)}\" to {count} clients.")

    async def _producer(self, message):
        self._future.set_result(message)


    async def send(self, message:Message):
        if self._future is None:
            return
        # await self._producer(message)
        asyncio.run_coroutine_threadsafe(self._producer(message), loop=self._loop)
        

