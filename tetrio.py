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
    "User-Agent": "Space Shuttle / 2.0 (https://github.com/patttterson/Space-Shuttle-Beta)"
}

async def get_player_data(usr: str):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(f"https://ch.tetr.io/api/users/{usr.lower()}/summaries/league") as response:
            return await response.json()

async def get_player_id(usr: str):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(f"https://ch.tetr.io/api/users/{usr.lower()}") as response:
            data = await response.json()
            return data["data"]["_id"]
