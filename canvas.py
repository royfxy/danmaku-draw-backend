from typing import OrderedDict
from orm import Model, StringField, IntegerField, TimestampField, Time
from collections import OrderedDict
import asyncio
import logging
from user import User
from websocket_sender import Message, MessageType


class Pixel(Model):
    __table__ = "pixel_history"

    _buffer = OrderedDict()
    _expire_time = 3
    _last_id = None

    @classmethod
    async def init(cls):
        cls._clear_buffer()
        await cls._set_last_id()

    @classmethod
    async def _set_last_id(cls):
        ids = await cls._sql.select('SELECT `id` FROM `%s` ORDER BY id DESC LIMIT 1' % (cls.__table__), [])
        if len(ids) == 0:
            last_id = 0
        else:
            last_id = ids[0][0]
        cls._last_id = last_id

    @classmethod
    def _clear_buffer(cls):
        cls._buffer = OrderedDict()

    @classmethod
    async def _discard(cls):
        count = 0
        while len(cls._buffer) > 0:
            key, pixel = cls._buffer.popitem(last=False)
            if Time.timestamp(Time.now()) - Time.timestamp(
                    pixel.time) <= cls._expire_time:
                cls._buffer[key] = pixel
                cls._buffer.move_to_end(key, last=False)
                break
            count += 1
        logging.debug(f"Removed {count} items from pixel history buffer.")

    @classmethod
    async def pixel(cls, user_id, pos, color_id):
        if user_id in cls._buffer:
            interval = Time.timestamp(Time.now()) - \
                Time.timestamp(cls._buffer[user_id].time)
            if interval <= cls._expire_time:
                logging.debug(
                    f"User {user_id} draw too frequently, {cls._expire_time - interval} seconds left.")
                return None
        await cls._discard()
        pixel = Pixel(pos=pos,
                      time=Time.now(),
                      color_id=color_id,
                      user_id=user_id)
        return pixel

    id = IntegerField('id', primary_key=True)
    pos = IntegerField('pos')
    time = TimestampField('time')
    color_id = IntegerField('color_id')
    user_id = IntegerField('user_id')

    def __init__(self, **kw):
        if Pixel._last_id is None:
            if "id" not in kw:
                raise RuntimeError("Run Canvas.init() first")
        else:
            Pixel._last_id += 1
            kw["id"] = Pixel._last_id

        super(Pixel, self).__init__(**kw)
        Pixel._buffer[self.user_id] = self
        logging.debug(f"Added user {self.user_id} to pixel history buffer.")


class Color(Model):
    __table__ = "color"

    colors = {}

    @classmethod
    async def init(cls):
        colors = await super().get_all()
        for color in colors:
            cls.colors[color.id] = color.hex

    @classmethod
    def get_hex(cls, color_id):
        if len(cls.colors) == 0:
            raise RuntimeError("Run Canvas.init() first")
        if color_id not in cls.colors:
            return None
        return cls.colors[color_id]

    id = IntegerField('id', primary_key=True)
    hex = StringField('hex', length=10)


class Canvas(Model):
    __table__ = "canvas"

    _canvas_row = None
    _canvas_col = None
    _canvas_buffer = None

    @classmethod
    def config(cls, col, row):
        cls._canvas_row = row
        cls._canvas_col = col
        cls._canvas_buffer = [None]*cls._canvas_col*cls._canvas_row

    @classmethod
    async def init(cls):
        await Color.init()
        canvas_pixels = await cls.get_all()
        if canvas_pixels:
            for canvas_pixel in canvas_pixels:
                pixel = await Pixel.find(canvas_pixel.pixel_id)
                cls._canvas_buffer[canvas_pixel.pos] = pixel.color_id
        await Pixel.init()

    @classmethod
    def _get_pos(cls, x, y):
        if x >= cls._canvas_col or x < 0 or y >= cls._canvas_row or y < 0:
            logging.debug(
                f"Position ({x}, {y}) out of range({cls._canvas_row}, {cls._canvas_col}).")
            return None
        return y + x * cls._canvas_col

    @classmethod
    async def draw(cls, user_id, x, y, color_id):
        pos = cls._get_pos(x, y)
        if pos is None:
            return None

        pixel = await Pixel.pixel(user_id, pos, color_id)
        if not pixel:
            return None
        canvas_pixel = Canvas(pos=pixel.pos, pixel_id=pixel.id)
        await pixel.save()
        await canvas_pixel.save_or_update()
        cls._canvas_buffer[pixel.pos] = pixel.color_id
        logging.debug(f"Pixel ({x}, {y}) drawed.")
        return pixel

    @classmethod
    def canvas(cls):
        data = {"col_num": cls._canvas_col, "row_num": cls._canvas_row,
                "colors": Color.colors, "pixels": cls._canvas_buffer}
        return Message(MessageType.INIT_CANVAS, data)

    pos = IntegerField('pos', primary_key=True)
    pixel_id = IntegerField('pixel_id')


async def draw_pixel(user_id, user_name, x, y, color_id):
    user = await User.user(uid=user_id, name=user_name)
    result = await Canvas.draw(user.uid, x, y, color_id)
    if result:
        user.dots_drawed += 1
        await user.save()
