from orm import Model, StringField, IntegerField
import logging

class User(Model):

    @classmethod
    async def find(cls, primary_key):
        user = await super(User, cls).find(primary_key)
        if user:
            logging.debug(f"User {primary_key} found in DB.")
            return user
        logging.debug(f"User {primary_key} not found.")
        return None

    @classmethod
    async def user(cls, **kw):
        user = await cls.find(kw["uid"])
        if not user:
            user = User(**kw)
            uid = kw["uid"]
            logging.debug(f"New user {uid} created.")
        elif "name" in kw and kw["name"] != user.name:
            user.name = kw["name"]
        return user

    async def save(self):
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
    vip_level = IntegerField('vip_level', default=0, column_type='int(4)')

    def __init__(self, **kw):
        super(User, self).__init__(**kw)
