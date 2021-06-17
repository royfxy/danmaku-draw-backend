from sql import SQL
import datetime
import logging

class Time:
    @classmethod
    def now(cls):
        return datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')

    @classmethod
    def timestamp(cls, time):
        if isinstance(time, datetime.datetime):
            return time.timestamp()
        return datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S').timestamp()
    
    @classmethod
    def fromtimestamp(cls, time):
        return datetime.datetime.strftime(datetime.datetime.fromtimestamp(time), '%Y-%m-%d %H:%M:%S')


class Field(object):
    def __init__(self,
                 name,
                 column_type,
                 primary_key,
                 default,
                 auto_increase=False):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
        self.auto_increase = primary_key if auto_increase else False

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type,
                                self.name)


class StringField(Field):
    def __init__(self, name, primary_key=False, default=None, length=100):
        super().__init__(name, f'varchar({length})', primary_key, default)


class IntegerField(Field):
    def __init__(self,
                 name,
                 primary_key=False,
                 default=None,
                 column_type='int',
                 auto_increase=False):
        super().__init__(name, column_type, primary_key, default,
                         auto_increase)


class TimestampField(Field):
    def __init__(self,
                 name,
                 primary_key=False,
                 default=None,
                 column_type='timestamp'):
        super().__init__(name, column_type, primary_key, default)


class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        table_name = attrs.get('__table__', None) or name
        mappings = dict()
        fields = []
        primary_key = None
        auto_increase = False
        for key, value in attrs.items():
            if isinstance(value, Field):
                mappings[key] = value
                if value.primary_key:
                    if primary_key:
                        raise RuntimeError(
                            "'Duplicate primary key for field: %s' %", key)
                    if value.auto_increase:
                        auto_increase = True
                    primary_key = key
                else:
                    fields.append(value.name)
        if not primary_key:
            raise RuntimeError('Primary key not found.')
        for key in mappings.keys():
            attrs.pop(key)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__auto_increase__'] = auto_increase
        attrs['__mappings__'] = mappings
        attrs['__table__'] = table_name
        attrs['__primary_key__'] = primary_key
        attrs['__fields__'] = fields
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (
            primary_key, ', '.join(escaped_fields), table_name)
        if auto_increase:
            attrs['__insert__'] = 'insert into `%s` (%s) values (%s)' % (
            table_name, ', '.join(escaped_fields), ",".join(
                ["?" for _ in range(len(escaped_fields))]))
        else:
            attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (
            table_name, ', '.join(escaped_fields), primary_key, ",".join(
                ["?" for _ in range(len(escaped_fields) + 1)]))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (
            table_name, ', '.join(
                map(lambda f: '`%s`=?' %
                    (mappings.get(f).name or f), fields)), primary_key)
        attrs[
            '__insertorupdate__'] = "INSERT INTO `%s` (%s, `%s`) VALUES (%s) ON DUPLICATE KEY UPDATE %s" % (
                table_name, ', '.join(escaped_fields), primary_key, ",".join([
                    "?" for _ in range(len(escaped_fields) + 1)
                ]), '=?, '.join(escaped_fields) + '=?')
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (table_name,
                                                                 primary_key)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    _sql = SQL()

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            value = self[key]
        except KeyError:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default
                setattr(self, key, value)
            else:
                raise AttributeError(r"'Model' object has no attribute '%s'" %
                                     key)
        return value

    def __setattr__(self, key, value):
        self[key] = value

    def get_value(self, key):
        return getattr(self, key, None)

    @classmethod
    async def find(cls, primary_key):
        ' find object by primary key. '
        rs = await cls._sql.select(
            '%s where `%s`=?' % (cls.__select__, cls.__primary_key__),
            [primary_key], 1)
        if len(rs) == 0:
            return None
        return cls(**dict(zip(cls.__mappings__.keys(), rs[0])))

    @classmethod
    async def get_all(cls):
        rs = await cls._sql.select('%s' % (cls.__select__), [])
        if len(rs) == 0:
            return None
        return [cls(**dict(zip(cls.__mappings__.keys(), r))) for r in rs]

    async def save(self):
        args = list(map(self.get_value, self.__fields__))
        if not self.__auto_increase__:
            args.append(self.get_value(self.__primary_key__))
        rows = await Model._sql.execute(self.__insert__, args)
        logging.debug('Insert record: affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.get_value, self.__fields__))
        args.append(self.get_value(self.__primary_key__))
        rows = await Model._sql.execute(self.__update__, args)
        logging.debug('Update record: affected rows: %s' % rows)

    async def delete(self):
        arg = self.get_value(self.__primary_key__)
        rows = await Model._sql.execute(self.__delete__, arg)
        logging.debug('Delete record: affected rows: %s' % rows)

    async def save_or_update(self):
        args = list(map(self.get_value, self.__fields__))
        args.append(self.get_value(self.__primary_key__))
        args += list(map(self.get_value, self.__fields__))
        rows = await Model._sql.execute(self.__insertorupdate__, args)
        logging.debug('Update or insert record: affected rows: %s' % rows)
