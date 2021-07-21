import asyncio
from music import Playlist
import blivedm.blivedm as blivedm
import re
from websocket_sender import Message, MessageType
from user import User
from canvas import Canvas

import logging

def get_range_num(x: str):
    try:
        single_num = int(x)
        return single_num, single_num
    except ValueError:
        nums_str = re.split(':|：', x)
        if len(nums_str) != 2:
            raise ValueError
        num1 = int(nums_str[0])
        num2 = int(nums_str[1])
        return num1, num2


class DanmakuClient(blivedm.BLiveClient):
    def __init__(self, room_id, handler, logger):
        super().__init__(room_id)
        self.start()
        self._handler = handler
        self._logger = logger

    async def _on_receive_danmaku(self, danmaku: blivedm.DanmakuMessage):
        self._logger.info(f'{danmaku.uname} {danmaku.uid}：{danmaku.msg}')
        await self._handler.parse_danmaku(danmaku)

    async def _on_receive_gift(self, gift: blivedm.GiftMessage):
        self._logger.info(
            f'{gift.uname} 赠送{gift.gift_name}x{gift.num} （{gift.coin_type}币x{gift.total_coin}）'
        )
        await self._handler.receive_gift(user_id=gift.uid,
                                         user_name=gift.uname,
                                         gift_name=gift.gift_name,
                                         gift_count=gift.num,
                                         coin_type=gift.coin_type,
                                         coin_count=gift.total_coin)

    async def _on_buy_guard(self, message: blivedm.GuardBuyMessage):
        self._logger.info(f'{message.username} 购买{message.gift_name}')


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

        tokens = re.split('-|—|－|﹣|﹣| ', text)
        length = len(tokens)
        if length == 1:
            if (tokens[0] == "切歌"):
                await self._skip_song(user_id=user_id, user_name=user_name)
            elif (tokens[0] == "点数"):
                await self._get_value(user_id=user_id, user_name=user_name)

        elif (tokens[0] == "点歌"):
            await self._add_song(user_id=user_id,
                                 user_name=user_name,
                                 query=" ".join(tokens[1:]))
        elif length == 3:
            try:
                pixel_count, x, y, color_id = self._parse_draw_op(tokens)
                await self._draw_pixel(user_id=user_id,
                                       user_name=user_name,
                                       pixel_count=pixel_count,
                                       x_start=x[0]-1,
                                       x_end=x[1]-1,
                                       y_start=y[0]-1,
                                       y_end=y[1]-1,
                                       color_id=color_id)
            except ValueError:
                pass

    async def receive_gift(self, user_id, user_name, gift_name, gift_count, coin_type, coin_count):
        user = await User.user(uid=user_id, name=user_name)
        if (coin_type == "silver" and coin_count > 0):
            user.silver_coin += coin_count
            if (user.vip_level < 1):
                user.vip_level = 1
            user.weight += int(coin_count/20)
            await user.save(force=True)
        elif (coin_type == "gold" and coin_count > 0):
            user.gold_coin += coin_count
            if (user.vip_level < 2):
                user.vip_level = 2
            user.weight += int(coin_count/5)
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

    async def change_weight(self, user_id, weight):
        user = await User.user(uid=user_id)
        user.weight += weight
        await user.save()

    def _parse_draw_op(self, tokens):
        x_1, x_2 = get_range_num(tokens[1])
        y_1, y_2 = get_range_num(tokens[0])
        x_start = min(x_1, x_2)
        x_end = max(x_1, x_2)
        y_start = min(y_1, y_2)
        y_end = max(y_1, y_2)
        color_id = int(tokens[2])
        pixel_count = (x_end - x_start + 1) * (y_end - y_start + 1)
        return pixel_count, (x_start, x_end), (y_start, y_end), color_id

    # draw a pixel on canvas
    async def _draw_pixel(self, user_id, user_name, pixel_count,
                          x_start, x_end, y_start, y_end, color_id):
        user = await User.user(uid=user_id, name=user_name)
        if pixel_count == 1:
            pixel = await Canvas.draw(user.uid, x_start, y_start, color_id)
            if pixel:
                data = {
                    "username": user.name,
                    "pos": pixel.pos,
                    "colorid": pixel.color_id
                }
                await self._canvas_ws.send(Message(MessageType.DRAW_PIXEL, data))
                user.dots_drawed += 1
                await self._message_ws.send(
                    Message(MessageType.TEXT_MESSAGE, {
                        "text": f"{user.name} 涂色: {y_start+1}-{x_start+1}-{color_id}",
                        "viplevel": user.vip_level
                    }))
        elif pixel_count >= 50:
            await self._message_ws.send(
                    Message(MessageType.TEXT_MESSAGE, {
                        "text": f"{user.name} 批量涂色失败: 一次涂不可以超过 50 个点哦",
                        "viplevel": user.vip_level
                    }))
            return
        else:
            if user.weight < pixel_count:
                await self._message_ws.send(
                    Message(MessageType.TEXT_MESSAGE, {
                        "text": f"{user.name} 批量涂色失败: 点数不足，剩余 {user.weight} 点",
                        "viplevel": user.vip_level
                    }))
                return
            pixels = await Canvas.draw_multiple(user.uid, x_start, x_end,
                                                y_start, y_end, color_id)
            data = {
                "username": user.name,
                "pos": [pixel.pos for pixel in pixels],
                "colorid": color_id
            }
            user.dots_drawed += len(pixels)
            if user.weight > 0:
                user.weight -= len(pixels)
                if user.weight < 0:
                    user.weight = 0
            await self._canvas_ws.send(Message(MessageType.DRAW_MULTIPLE_PIXELS, data))
            await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 批量涂色成功，剩余点数: {user.weight}",
                        "viplevel": user.vip_level
                        }))
        await user.save()

    # skip playing song
    async def _skip_song(self, user_id, user_name):
        user = await User.user(uid=user_id, name=user_name)
        if Playlist.playing().user_id == 0 or user_id == Playlist.playing().user_id:
            await Playlist.skip()
            await self._message_ws.send(await Playlist.playlist())
            await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 切歌成功",
                    "viplevel": user.vip_level
                }))

    async def _add_song(self, user_id, user_name, query):
        user = await User.user(uid=user_id, name=user_name)
        song = await Playlist.add(user, query)

        if song:
            await self._message_ws.send(await Playlist.playlist())
            user.music_ordered += 1
            await user.save()
            await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 点歌: {song.song_name}",
                    "viplevel": user.vip_level
                }))

    async def _get_value(self, user_id, user_name):
        user = await User.user(uid=user_id, name=user_name)
        await self._message_ws.send(
                Message(MessageType.TEXT_MESSAGE, {
                    "text": f"{user.name} 剩余点数: {user.weight}",
                    "viplevel": user.vip_level
                }))
