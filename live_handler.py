import asyncio
from music import Playlist
import blivedm.blivedm as blivedm
import re
from websocket_sender import Message, MessageType
from user import User
from canvas import Canvas

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

    async def _on_receive_danmaku(self, danmaku: blivedm.DanmakuMessage):
        logging.info(f'{danmaku.uname} {danmaku.uid}：{danmaku.msg}')
        await self._handler.parse_danmaku(danmaku)

    async def _on_receive_gift(self, gift: blivedm.GiftMessage):
        logging.info(
            f'{gift.uname} 赠送{gift.gift_name}x{gift.num} （{gift.coin_type}币x{gift.total_coin}）'
        )
        await self._handler.receive_gift(user_id=gift.uid,
                                         user_name=gift.uname,
                                         gift_name=gift.gift_name,
                                         gift_count=gift.num,
                                         coin_type=gift.coin_type,
                                         coin_count=gift.total_coin)

    async def _on_buy_guard(self, message: blivedm.GuardBuyMessage):
        logging.info(f'{message.username} 购买{message.gift_name}')


class LiveHandler:
    def __init__(self, message_sender, canvas_sender, init_message):
        self._message_ws = message_sender
        self._canvas_ws = canvas_sender
        self.init_message = init_message
        asyncio.get_event_loop().create_task(Canvas.init())

    async def parse_danmaku(self, message: blivedm.DanmakuMessage):
        text = message.msg
        user_id = message.uid
        user_name = message.uname

        tokens = re.split('-|—|－|﹣|﹣', text)
        length = len(tokens)
        if length == 1:
            if (tokens[0] == "切歌"):
                await self._skip_song(user_id=user_id, user_name=user_name)

        elif (tokens[0] == "点歌"):
            await self._add_song(user_id=user_id,
                                 user_name=user_name,
                                 query=" ".join(tokens[1:]))
        nums = self._parse_nums(tokens)
        if nums is not None:
            if length == 3:
                await self._draw_pixel(user_id=user_id,
                                       user_name=user_name,
                                       x=nums[1]-1,
                                       y=nums[0]-1,
                                       color_id=nums[2])

    async def receive_gift(self, user_id, user_name, gift_name, gift_count, coin_type, coin_count):
        user = await User.user(uid=user_id, name=user_name)
        if (coin_type == "silver" and coin_count > 0):
            user.silver_coin += coin_count
            if (user.vip_level < 1):
                user.vip_level = 1
        elif (coin_type == "gold" and coin_count > 0):
            user.gold_coin += coin_count
            if (user.vip_level < 2):
                user.vip_level = 2
        
        await user.save(force=True)
        data = {
            "username": user_name,
            "giftname": gift_name,
            "giftcount": gift_count,
        }
        await self._message_ws.send(Message(MessageType.RECEIVE_GIFT, data))
        await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"感谢 {user.name} 送的 {gift_name} {gift_count} 个",
                    "viplevel": user.vip_level
                }))

    def get_init_message(self):
        return Message(MessageType.INIT_MESSAGE, self.init_message)

    def store_all(self):
        asyncio.get_event_loop().create_task(User.store_all())
        logging.info(f"All data stored to DB.")

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
                "username": user.name,
                "pos": pixel.pos,
                "colorid": pixel.color_id
            }
            await self._canvas_ws.send(Message(MessageType.DRAW_PIXEL, data))
            user.dots_drawed += 1
            await user.save()
            await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 涂色: {y+1}-{x+1}-{color_id}",
                    "viplevel": user.vip_level
                }))

    # skip song
    async def _skip_song(self, user_id, user_name):
        user = await User.user(uid=user_id, name=user_name)
        if user_id == Playlist.playing()["user_id"]:
            Playlist.skip()
        await self._message_ws.send(Playlist.playlist())
        await self._message_ws.send(
            Message(MessageType.TEXT_MESSAGE, {
                "text": f"{user.name} 切歌成功",
                "viplevel": user.vip_level
            }))

    async def _add_song(self, user_id, user_name, query):
        user = await User.user(uid=user_id, name=user_name)
        song = await Playlist.add(user, query)
        if song:
            await self._message_ws.send(Playlist.playlist())
            user.music_ordered += 1
            await user.save()
            await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 点歌: {song.song_name}",
                    "viplevel": user.vip_level
                }))