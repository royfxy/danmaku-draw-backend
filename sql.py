import aiomysql
import asyncio
import os
from singleton import singleton
from dotenv import load_dotenv

load_dotenv()

a = os.getenv("DB_PORT")

@singleton
class SQL:
    def __init__(self):
        self._pool = asyncio.get_event_loop().create_future()
        asyncio.get_event_loop().create_task(self.init_pool())
        asyncio.get_event_loop().create_task(self._keep_alive())

    async def init_pool(self):
        try:
            self._pool.set_result(await aiomysql.create_pool(
                minsize=5,
                maxsize=10,
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT")),
                user=os.getenv("DB_USERNAME"),
                charset='utf8mb4',
                password=os.getenv("DB_PASSWORD"),
                db=os.getenv("DB_NAME"),
                autocommit=True,
            ))
        except Exception:
            print("connection error")

    async def get_pool(self):
        return await self._pool

    async def _keep_alive(self):
        pool = await self.get_pool()
        while True:
            await asyncio.sleep(10)
            async with pool.acquire() as connection:
                print("ping")
                await connection.ping()

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

    async def execute3(self, query, param=None):
        connection, cursor = await self.getCurosr()
        try:
            await cursor.execute(query.replace('?', '%s'), param)
            affected = cursor.rowcount
            # await connection.commit()
            return affected
        except BaseException as e:
            raise
        finally:
            if cursor:
                await cursor.close()
            await self._pool.release(connection)
