import aiomysql
import asyncio
from singleton import singleton
import logging


@singleton
class SQL:
    def __init__(self):
        self._pool = asyncio.get_event_loop().create_future()

    def connect(self, host, port, db, username, password):
        self.host = host
        self.port = port
        self.db = db
        self.username = username
        self.password = password
        asyncio.get_event_loop().create_task(
            self._init_pool(host, port, db, username, password))
        asyncio.get_event_loop().create_task(self._keep_alive())

    async def _init_pool(self, host, port, db, username, password):
        try:
            self._pool.set_result(await aiomysql.create_pool(
                minsize=5,
                maxsize=10,
                host=host,
                port=port,
                db=db,
                user=username,
                password=password,
                charset='utf8mb4',
                autocommit=True,
            ))
            logging.debug(
                ("Successfully connect to SQL: "
                 f"{db} on {host}:{port} as {username}"))
        except Exception:
            logging.error("SQL connection failure")

    async def get_pool(self):
        return await self._pool

    async def _keep_alive(self):
        pool = await self.get_pool()
        while True:
            try:
                await asyncio.sleep(10)
                async with pool.acquire() as connection:
                    await connection.ping()
                    logging.debug("SQL ping sent")
            except Exception:
                logging.warning("Lost SQL connection, reconnecting...")
                await self.connect(self.host, self.port, self.db,
                                   self.username, self.password)

    async def select(self, query, param=None, size=None):
        pool = await self.get_pool()
        async with pool.acquire() as connection:
            cursor = await connection.cursor()
            await cursor.execute(query.replace('?', '%s'), param)
            if size:
                return await cursor.fetchmany(size)
            return await cursor.fetchall()

    async def execute(self, query, param=None, size=None):
        pool = await self.get_pool()
        async with pool.acquire() as connection:
            cursor = await connection.cursor()
            await cursor.execute(query.replace('?', '%s'), param)
            affected = cursor.rowcount
            return affected
