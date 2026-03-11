import time

import aiohttp

ranks = {
    "x+": 1,
    "x": 2,
    "u": 3,
    "ss": 4,
    "s+": 5,
    "s": 6,
    "s-": 7,
    "a+": 8,
    "a": 9,
    "a-": 10,
    "b+": 11,
    "b": 12,
    "b-": 13,
    "c+": 14,
    "c": 15,
    "c-": 16,
    "d+": 17,
    "d": 18,
}

HEADERS = {
    "User-Agent": "Space Shuttle / 2.0 (https://github.com/patttterson/Space-Shuttle-Beta)",
    "X-Session-ID": "PQKPuKUFQ2Ru3ggdr47DAA"
}

_cache: dict[str, tuple[dict, int]] = {}  # url -> (response_data, cached_until ms)

async def _get(url: str) -> tuple[dict, int | None]:
    now_ms = int(time.time() * 1000)
    if url in _cache:
        data, cached_until = _cache[url]
        if now_ms < cached_until:
            return data, cached_until
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            data = await response.json()
    cached_until = None
    if "cache" in data:
        cached_until = data["cache"]["cached_until"]
        _cache[url] = (data, cached_until)
    return data, cached_until

def _invalidate_user_cache(usr: str) -> None:
    usr = usr.lower()
    for url in list(_cache.keys()):
        if f"/users/{usr}" in url:
            del _cache[url]

def _invalidate_user_id_cache(id: str) -> None:
    for url in list(_cache.keys()):
        if f"/users/search/discord:id:{id}" in url:
            del _cache[url]

async def get_player_tl_data(usr: str) -> tuple[dict, int | None]:
    return await _get(f"https://ch.tetr.io/api/users/{usr.lower()}/summaries/league")

async def get_player(usr: str) -> tuple[dict, int | None]:
    """Return Type: ({ _id: str, username: str, ... }, cached_until_ms)"""
    data, cached_until = await _get(f"https://ch.tetr.io/api/users/{usr.lower()}")
    return data["data"], cached_until

async def reverse_player_lookup(id: str) -> tuple[dict, int | None]:
    """Return Type: ({ _id: str, username: str }, cached_until_ms)"""
    data, cached_until = await _get(f"https://ch.tetr.io/api/users/search/discord:id:{id}")
    return data["data"], cached_until
