from asyncio.events import get_event_loop
import asyncio
from music import Playlist
import blivedm.blivedm as blivedm
import re
from websocket_sender import WebsocketSender, Message, MessageType
from user import User
from canvas import Canvas, Pixel

import logging


def get_num(x: str):
    try:
        return int(x)
    except ValueError:
        return None


class DanmakuClient(blivedm.BLiveClient):
    def __init__(self, room_id, handler):
        super().__init__(room_id)
        self.start()
        self._handler = handler

    async def _on_receive_popularity(self, popularity: int):
        logging.info(f'当前人气值：{popularity}')

    async def _on_receive_danmaku(self, danmaku: blivedm.DanmakuMessage):
        logging.info(f'{danmaku.uname} {danmaku.uid}：{danmaku.msg}')
        await self._handler.parse_danmaku(danmaku)

    async def _on_receive_gift(self, gift: blivedm.GiftMessage):
        logging.info(
            f'{gift.uname} 赠送{gift.gift_name}x{gift.num} （{gift.coin_type}币x{gift.total_coin}）'
        )

    async def _on_buy_guard(self, message: blivedm.GuardBuyMessage):
        logging.info(f'{message.username} 购买{message.gift_name}')

    async def _on_super_chat(self, message: blivedm.SuperChatMessage):
        logging.info(
            f'醒目留言 ¥{message.price} {message.uname}：{message.message}')


class LiveHandler:
    def __init__(self, message_sender, canvas_sender):
        self._message_ws = message_sender
        self._canvas_ws = canvas_sender
        asyncio.get_event_loop().create_task(Canvas.init())

    async def parse_danmaku(self, message: blivedm.DanmakuMessage):
        text = message.msg
        user_id = message.uid
        user_name = message.uname

        tokens = re.split('-|—|－|﹣|﹣', text)
        length = len(tokens)
        if length == 1:
            if (tokens[0] == "切歌"):
                await self._skip_song(user_id=user_id)
        elif length == 2:
            if (tokens[0] == "点歌"):
                await self._add_song(user_id=user_id,
                                     user_name=user_name,
                                     query=tokens[1])
        nums = self._parse_nums(tokens)
        if nums is not None:
            if length == 3:
                await self._draw_pixel(user_id=user_id,
                                       user_name=user_name,
                                       x=nums[1]-1,
                                       y=nums[0]-1,
                                       color_id=nums[2])

    def _parse_nums(self, tokens):
        nums = []
        for token in tokens:
            num = get_num(token)
            if num == None:
                return None
            nums.append(num)
        return nums

    # draw a pixel on canvas
    async def _draw_pixel(self, user_id, user_name, x, y, color_id):
        user = await User.user(uid=user_id, name=user_name)
        pixel = await Canvas.draw(user.uid, x, y, color_id)
        if pixel:
            data = {
                "name": user.name,
                "pos": pixel.pos,
                "color_id": pixel.color_id
            }
            await self._canvas_ws.send(Message(MessageType.DRAW_PIXEL, data))
            user.dots_drawed += 1
            await user.save()

    # skip song
    async def _skip_song(self, user_id):
        if user_id == Playlist.playing()["user_id"]:
            Playlist.skip()
        await self._message_ws.send(Playlist.playlist())

    async def _add_song(self, user_id, user_name, query):
        user = await User.user(uid=user_id, name=user_name)
        playlist = await Playlist.add(user, query)
        if playlist:
            await self._message_ws.send(Playlist.playlist())
            user.music_ordered += 1
            await user.save()

    def store_all(self):
        asyncio.get_event_loop().run_until_complete(User.store_all())
        logging.info(f"All data stored to DB.")
