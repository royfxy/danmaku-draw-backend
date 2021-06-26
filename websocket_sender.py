import asyncio
import websockets
import threading
import json
from enum import Enum, unique

import logging

@unique
class MessageType(Enum):
    DRAW_PIXEL = 0
    DRAW_SUBPIXEL = 1
    TEXT_MESSAGE = 2
    UPDATE_PLAYLIST = 3
    PLAY_SONG = 4
    SKIP_SONG = 5
    INIT_CANVAS = 6
    INIT_MESSAGE = 7
    RECEIVE_GIFT = 8


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
        self._name = str(ip) + ':' + str(port)
        self._loop = asyncio.get_event_loop()
        self._future = None
        self._future_lock = None
        self._clients = set()
        self._start()
    
    # start a new thread to handle websocket
    def _start(self):
        asyncio.get_event_loop().run_until_complete(websockets.serve(self._connect, self._ip, self._port))
        # asyncio.ensure_future(websockets.serve(self._connect, self._ip, self._port))

    async def _connect(self, websocket, path):
        self._clients.add(websocket)
        logging.debug(f"New websocket connection to {self._name}")
        while True:
            self._future = self._loop.create_future()
            message = await self._future
            self._future_lock.set_result(True)
            count = 0

            # send message to all connected clients
            for ws in list(self._clients):
                try:
                    await ws.send(str(message))
                    count += 1
                except websockets.exceptions.ConnectionClosed:
                    self._clients.remove(ws)
                except TypeError:
                    pass
            logging.debug(f"Websocket {self._name} sent message \"{str(message)}\" to {count} clients.")

    async def send(self, message:Message):
        if self._future is None:
            logging.warning(f"Websocket {self._name} future not ready.")
            return
        self._future_lock = self._loop.create_future()
        self._future.set_result(message)
        await self._future_lock


        
