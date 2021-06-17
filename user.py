from collections import OrderedDict
from orm import Model, StringField, IntegerField
import asyncio
import random
import logging

class User(Model):
    _buffer_size = 5
    _lru_discard_size = 2
    _buffer = OrderedDict()

    @classmethod
    async def find(cls, primary_key):
        if primary_key in cls._buffer:
            user = cls._buffer[primary_key]
            logging.debug(f"User {primary_key} found in user buffer.")
        else:
            user = await super(User, cls).find(primary_key)
            if user:
                logging.debug(f"User {primary_key} found in DB.")
            
        if user:
            return user

        logging.debug(f"User {primary_key} not found.")
        return None
        

    @classmethod
    async def store_all(cls):
        count = 0
        for user in cls._buffer.values():
            await user.save(force=True)
            count += 1
        logging.info(f"All {count} users in buffer saved to DB.")

    @classmethod
    async def _visit(cls, user):
        uid = user.uid
        if uid in cls._buffer:
            cls._buffer.move_to_end(uid)
            logging.debug(f"User {uid} moved to buffer head.")
        else:
            cls._buffer[uid] = user
            logging.debug(f"User {uid} added to buffer.")
        await cls._lru()

    @classmethod
    async def _lru(cls):
        if len(cls._buffer) < cls._buffer_size:
            return
        count = 0
        while len(cls._buffer) > cls._buffer_size - cls._lru_discard_size:
            if len(cls._buffer) == 0:
                break
            _, user = cls._buffer.popitem(last=False)
            await user.save(force=True)
            count += 1
        logging.debug(f"Removed {count} items from user buffer and saved to DB.")

    @classmethod
    async def user(cls, **kw):
        user = await cls.find(kw["uid"])
        if not user:
            user = User(**kw)
        await User._visit(user)
        return user

    async def save(self, force=False):
        if not force:
            await User._visit(self)
        else:
            logging.debug(f"User {self.uid} saved to DB.")
            await super().save_or_update()

    __table__ = "user"
    uid = IntegerField('uid', primary_key=True)
    name = StringField('name', length=20)
    gold_coin = IntegerField('gold_coin',
                             default=0,
                             column_type='int unsigned')
    silver_coin = IntegerField('silver_coin',
                               default=0,
                               column_type='int unsigned')
    music_ordered = IntegerField('music_ordered',
                                 default=0,
                                 column_type='int unsigned')
    dots_drawed = IntegerField('dots_drawed',
                               default=0,
                               column_type='int unsigned')
    weight = IntegerField('weight', default=10, column_type='int unsigned')

    def __init__(self, **kw):
        super(User, self).__init__(**kw)
        User._buffer[self.uid] = self
        uid = kw["uid"]
        logging.debug(f"New user {uid} created.")
