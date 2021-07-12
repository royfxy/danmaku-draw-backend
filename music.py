import json
import aiohttp
import logging
import random

from websocket_sender import Message, MessageType


class EmptyError(Exception):
    pass


class NetworkError(Exception):
    pass


class MusicService:
    def __init__(self, port, ip='localhost', cookie=None):
        self._port = port
        self._ip = ip
        self._payload = {}
        if cookie is not None:
            self._payload["cookie"] = cookie
        self.base_url = f"http://{ip}:{port}"

    async def _get(self, path, payload):
        payload.update(self._payload)
        logging.debug(f"Getting {path}, payload: {payload}")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url + path,
                                   params=payload) as response:
                if response.status != 200:
                    logging.warning(
                        f"Music service not avaliable, code:{response.status}."
                    )
                    raise NetworkError
                html = await response.text()
        return html

    async def search(self, query):
        path = "/search"
        payload = {'keywords': query}

        result_raw = await self._get(path, payload)
        result = json.loads(result_raw)['result']['songs']
        if len(result) == 0:
            raise EmptyError
        music_id = result[0]['id']
        title = result[0]['name']
        artists = ", ".join([x["name"] for x in result[0]['artists']])
        return music_id, title, artists

    async def get_info(self, id):
        path = "/song/detail"
        payload = {'ids': id}
        result_raw = await self._get(path, payload)

        result = json.loads(result_raw)["songs"][0]

        name = result['name']
        artists = [x['name'] for x in result['ar']]
        cover = result['al']['picUrl'] + "?param=100y100"
        return {'id': id, 'name': name, 'artists': artists, "cover_url": cover}

    async def get_play_url(self, id):
        path = "/song/url"
        payload = {'id': id, 'br':192000}
        result_raw = await self._get(path, payload)
        result = json.loads(result_raw)['data'][0]
        return result['url']


class Song:
    def __init__(self, user_id, user_name, song_id, song_name, artists,
                 weight):
        self.user_id = user_id
        self.user_name = user_name
        self.song_id = song_id
        self.song_name = song_name
        self.artists = artists
        self.weight = weight

    def json(self):
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "song_id": self.song_id,
            "song_name": self.song_name,
            "artists": self.artists
        }


class Playlist:
    _service = None
    _playlist = []
    _user_song_count = {}
    _limit_per_user = 2
    _total_limit = 50

    _default_playlist = []
    _last_random_index = None
    _random_song = None

    @classmethod
    def set_serivce(cls, music_service):
        cls._service = music_service

    @classmethod
    async def add(cls, user, query):
        if len(cls._playlist) >= cls._total_limit:
            return None
        if user.uid in cls._user_song_count and cls._user_song_count[
                user.uid] >= cls._limit_per_user:
            return None
        try:
            song_id, song_name, artists = await cls._service.search(query)
        except EmptyError:
            return None
        except NetworkError:
            return None

        weight = user.weight

        song = Song(user_id=user.uid,
                    user_name=user.name,
                    song_id=song_id,
                    song_name=song_name,
                    artists=artists,
                    weight=weight)
        if user.uid in cls._user_song_count:
            cls._user_song_count[user.uid] += 1
        else:
            cls._user_song_count[user.uid] = 1
        if len(cls._playlist) == 0 or weight <= cls._playlist[-1].weight:
            cls._playlist.append(song)
        else:
            for i in range(1, len(cls._playlist)):
                if (cls._playlist[i].weight >= weight):
                    continue
                cls._playlist.insert(i, song)
                break
        logging.debug(f"Song {song.song_id} added to playlist.")
        return song

    @classmethod
    @property
    def default_palylist(cls):
        return cls._default_playlist

    @classmethod
    def add_to_default(cls, query):
        if query not in cls._default_playlist:
            cls._default_playlist.append(query)

    @classmethod
    async def new_random_song(cls):
        defalut_playlist_length = len(cls._default_playlist)
        if defalut_playlist_length == 0:
            return None
        while True:
            random_index = random.randint(0, defalut_playlist_length - 1)
            if (random_index != cls._last_random_index or 
                len(cls._default_playlist) <= 1):
                cls._last_random_index = random_index
                break
        query = cls._default_playlist[random_index]
        try:
            song_id, song_name, artists = await cls._service.search(query)
        except EmptyError:
            return None
        except NetworkError:
            return None
        cls._random_song = Song(user_id=0,
                    user_name="系统",
                    song_id=song_id,
                    song_name=song_name,
                    artists=artists,
                    weight=0)

    @classmethod
    def playing(cls):
        if len(cls._playlist) == 0:
            return cls._random_song
        return cls._playlist[0]

    @classmethod
    async def playlist(cls):
        if len(cls._playlist) == 0:
            if cls._random_song is None:
                await cls.new_random_song()
            random_song = cls._random_song
            return Message(MessageType.UPDATE_PLAYLIST, [random_song.json()])
        return Message(MessageType.UPDATE_PLAYLIST, [song.json() for song in cls._playlist])

    @classmethod
    async def play(cls):
        if len(cls._playlist) == 0:
            song = cls._random_song
        else:
            song = cls._playlist[0]
        first_id = song.song_id
        info = await cls._service.get_info(first_id)
        play_url = await cls._service.get_play_url(first_id)
        succeed = not play_url is None
        logging.debug(f"Song {song.song_name} playing.")
        return succeed, Message(MessageType.PLAY_SONG, {"info": info, "play_url": play_url, "user_name": song.user_name})

    @classmethod
    async def skip(cls):
        if len(cls._playlist) == 0:
            await cls.new_random_song()
        else:
            song = cls._playlist.pop(0)
            cls._user_song_count[song.user_id] -= 1
            if cls._user_song_count[song.user_id] == 0:
                del cls._user_song_count[song.user_id]
        logging.debug(f"Song skipped.")
        return True
