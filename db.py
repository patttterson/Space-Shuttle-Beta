from __future__ import annotations

import csv
import os

import asqlite

_con: asqlite.Connection | None = None


async def init() -> None:
    global _con
    _con = await asqlite.connect("registrations.db")
    await _con.execute("CREATE TABLE IF NOT EXISTS registration(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, discord_id BIGINT, discord_username VARCHAR(256), tournament_name VARCHAR(256), server_id BIGINT, game_username VARCHAR(256), challonge_id BIGINT, rating FLOAT)")
    await _con.execute("CREATE TABLE IF NOT EXISTS thread(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, discord_id BIGINT, server_id BIGINT, challonge_match_id BIGINT, state VARCHAR(32), challonge_player1_id BIGINT, challonge_player2_id BIGINT, tournament_url VARCHAR(64))")
    await _con.execute("CREATE TABLE IF NOT EXISTS tournament(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, tournament_name VARCHAR(128), thread_channel BIGINT, participant_role BIGINT, server_id BIGINT, registrations_open BOOLEAN, is_tetrio BOOLEAN, rank_cap VARCHAR(8), rank_floor VARCHAR(8))")
    await _con.execute("CREATE TABLE IF NOT EXISTS serverSetting(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, server_id BIGINT, logging_channel BIGINT, registration_channel BIGINT, registration_info_id BIGINT, registration_id BIGINT, max_active_brackets INT DEFAULT 5)")
    await _con.execute("CREATE TABLE IF NOT EXISTS bracket(timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, tournament_url VARCHAR(256), tournament_name VARCHAR(128), server_id BIGINT, is_open BOOLEAN)")
    await _con.commit()

async def execute_dql(sql: str) -> None:
    assert _con is not None
    cur = await _con.execute(sql)
    rows = await cur.fetchall()
    os.makedirs('exports', exist_ok=True)
    with open('exports/return.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        if rows:
            writer.writerow(rows[0].keys())
        writer.writerows([tuple(row) for row in rows])


async def execute_dml(sql: str) -> None:
    assert _con is not None
    await _con.execute(sql)
    await _con.commit()


async def check_if_tournament_exists(tournament_name: str, guild_id: int) -> bool:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) FROM tournament WHERE tournament_name = ? AND server_id = ?", (tournament_name, guild_id))
    data = await cur.fetchall()
    return data[0][0] != 0


async def insert_tournament(tournament_name: str, guild_id: int, thread_channel: int | None = None, is_tetrio: bool = False, rank_cap: str | None = None, rank_floor: str | None = None, participant_role: int | None = None) -> None:
    assert _con is not None
    await _con.execute("INSERT INTO tournament (thread_channel, participant_role, tournament_name, server_id, registrations_open, is_tetrio, rank_cap, rank_floor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (thread_channel, participant_role, tournament_name, guild_id, True, is_tetrio, rank_cap, rank_floor))
    await _con.commit()


async def get_tournaments_by_server(guild_id: int) -> list:
    assert _con is not None
    cur = await _con.execute("SELECT * FROM tournament WHERE server_id = ? ORDER BY timestamp DESC", (guild_id,))
    data = await cur.fetchall()
    col = list(data[0].keys()) if data else []
    return [col] + [tuple(row) for row in data]


async def remove_tournament(guild_id: int, tournament_name: str) -> None:
    assert _con is not None
    await _con.execute("DELETE FROM thread WHERE server_id = ? AND tournament_url in (SELECT tournament_url FROM bracket WHERE tournament_name = ? AND server_id = ?)", (guild_id, tournament_name, guild_id))
    await _con.execute("DELETE FROM bracket WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    await _con.execute("DELETE FROM registration WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    await _con.execute("DELETE FROM tournament WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    await _con.commit()
    #TODO test that removing a tournament also removes records from the other tables so that the tournament namespace is properly restored to normal


async def set_tournament_registrations_state(guild_id: int, tournament_name: str, state: bool) -> None:
    assert _con is not None
    await _con.execute("UPDATE tournament SET registrations_open = ? WHERE server_id = ? AND tournament_name = ?", (state, guild_id, tournament_name))
    await _con.commit()


async def configure_server_if_not_setup(guild_id: int) -> None:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) FROM serverSetting WHERE server_id = ?", (guild_id,))
    data = await cur.fetchall()
    if data[0][0] == 0:
        await _con.execute("INSERT INTO serverSetting (server_id) VALUES (?)", (guild_id,))
        await _con.commit()


async def set_logging_channel(guild_id: int, channel_id: int) -> None:
    assert _con is not None
    await _con.execute("UPDATE serverSetting SET logging_channel = ? WHERE server_id = ?", (channel_id, guild_id))
    await _con.commit()


async def set_registration_channel(guild_id: int, channel_id: int) -> None:
    assert _con is not None
    await _con.execute("UPDATE serverSetting SET registration_channel = ? WHERE server_id = ?", (channel_id, guild_id))
    await _con.commit()


async def set_registration_messages(guild_id: int, message_1_id: int, message_2_id: int) -> None:
    assert _con is not None
    await _con.execute("UPDATE serverSetting SET registration_info_id = ?, registration_id = ? WHERE server_id = ?", (message_1_id, message_2_id, guild_id))
    await _con.commit()


async def check_if_player_registered_for_tournament(guild_id: int, user_id: int, tournament_name: str) -> bool:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) FROM registration WHERE server_id = ? AND discord_id = ? AND tournament_name = ?", (guild_id, user_id, tournament_name))
    data = await cur.fetchall()
    return data[0][0] != 0


async def check_if_username_registered_for_tournament(guild_id: int, tournament_name: str, game_username: str) -> bool:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) FROM registration WHERE server_id = ? AND tournament_name = ? AND game_username = ?", (guild_id, tournament_name, game_username))
    data = await cur.fetchall()
    return data[0][0] != 0


async def remove_from_tournament(guild_id: int, user_id: int, tournament_name: str) -> None:
    assert _con is not None
    await _con.execute("DELETE FROM registration WHERE server_id = ? AND discord_id = ? AND tournament_name = ?", (guild_id, user_id, tournament_name))
    await _con.commit()


async def is_tournament_tetrio(guild_id: int, tournament_name: str) -> bool:
    assert _con is not None
    cur = await _con.execute("SELECT is_tetrio FROM tournament WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    data = await cur.fetchall()
    if len(data) == 0:
        return False
    return data[0][0]


async def get_logging_channel(guild_id: int) -> int | None:
    assert _con is not None
    cur = await _con.execute("SELECT logging_channel FROM serverSetting WHERE server_id = ?", (guild_id,))
    data = await cur.fetchall()
    return data[0][0]


async def insert_into_tournament(discord_id: int, discord_username: str, server_id: int, tournament_name: str, rating: float, game_username: str | None = None) -> None:
    assert _con is not None
    await _con.execute("INSERT INTO registration (discord_id, discord_username, server_id, tournament_name, rating, game_username) VALUES (?, ?, ?, ?, ?, ?)", (discord_id, discord_username, server_id, tournament_name, rating, game_username))
    await _con.commit()


async def get_floor_and_cap(guild_id: int, tournament_name: str) -> tuple[str | None, str | None]:
    assert _con is not None
    cur = await _con.execute("SELECT rank_floor, rank_cap FROM tournament WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    data = await cur.fetchall()
    return tuple(data[0])  # type: ignore[return-value]


async def get_open_tournaments(guild_id: int) -> list[str]:
    assert _con is not None
    cur = await _con.execute("SELECT tournament_name FROM tournament WHERE server_id = ? AND registrations_open = TRUE", (guild_id,))
    data = await cur.fetchall()
    return [row[0] for row in data]


async def get_tournament_role(guild_id: int, tournament_name: str) -> int | None:
    assert _con is not None
    cur = await _con.execute("SELECT participant_role FROM tournament WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    data = await cur.fetchall()
    return None if len(data) == 0 else data[0][0]


async def get_registration_messages_info(guild_id: int) -> list[int]:
    assert _con is not None
    cur = await _con.execute("SELECT registration_channel, registration_id, registration_info_id FROM serverSetting WHERE server_id = ?", (guild_id,))
    data = await cur.fetchall()
    return list(data[0])


async def get_guilds() -> list[int]:
    assert _con is not None
    cur = await _con.execute("SELECT server_id FROM serverSetting")
    data = await cur.fetchall()
    return [row[0] for row in data]


async def get_participant_count(guild_id: int, tournament_name: str) -> int:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) FROM registration WHERE tournament_name = ? AND server_id = ?", (tournament_name, guild_id))
    data = await cur.fetchall()
    return data[0][0]


async def get_participant_counts(guild_id: int) -> list:
    assert _con is not None
    cur = await _con.execute("SELECT COUNT(*) AS player_count, tournament_name FROM registration WHERE server_id = ? GROUP BY tournament_name ORDER BY timestamp DESC", (guild_id,))
    data = await cur.fetchall()
    col = list(data[0].keys()) if data else []
    return [col] + [tuple(row) for row in data]


async def export_participants_full(guild_id: int, tournament_name: str) -> list:
    assert _con is not None
    cur = await _con.execute("SELECT * FROM registration WHERE server_id = ? AND tournament_name = ? ORDER BY rating DESC", (guild_id, tournament_name))
    data = await cur.fetchall()
    col = list(data[0].keys()) if data else []
    return [col] + [tuple(row) for row in data]


async def export_participants(guild_id: int, tournament_name: str) -> list:
    assert _con is not None
    cur = await _con.execute("SELECT discord_username FROM registration WHERE server_id = ? AND tournament_name = ? ORDER BY rating DESC", (guild_id, tournament_name))
    data = await cur.fetchall()
    col = list(data[0].keys()) if data else []
    return [col] + [tuple(row) for row in data]


async def export_participants_if_in_set(guild_id: int, tournament_name: str, participant_list: set[int]) -> list:
    assert _con is not None
    args = (guild_id, tournament_name, *participant_list)
    placeholders = ("?," * len(participant_list))[:-1]
    cur = await _con.execute(f"SELECT discord_username FROM registration WHERE server_id = ? AND tournament_name = ? AND discord_id IN ({placeholders}) ORDER BY rating DESC", args)
    data = await cur.fetchall()
    col = list(data[0].keys()) if data else []
    return [col] + [tuple(row) for row in data]


async def update_rating(guild_id: int, tournament_name: str, game_username: str, new_rating: float) -> None:
    assert _con is not None
    await _con.execute("UPDATE registration SET rating = ? WHERE server_id = ? AND tournament_name = ? AND game_username = ?", (new_rating, guild_id, tournament_name, game_username))
    await _con.commit()


async def get_game_users_from_tournament(guild_id: int, tournament_name: str) -> list[str]:
    assert _con is not None
    cur = await _con.execute("SELECT game_username FROM registration WHERE server_id = ? AND tournament_name = ?", (guild_id, tournament_name))
    data = await cur.fetchall()
    return [row[0] for row in data]


async def get_discord_user_from_game_username(guild_id: int, tournament_name: str, game_username: str) -> tuple[int, str]:
    assert _con is not None
    cur = await _con.execute("SELECT discord_id, discord_username FROM registration WHERE server_id = ? AND tournament_name = ? AND game_username = ?", (guild_id, tournament_name, game_username))
    data = await cur.fetchall()
    return tuple(data[0])  # type: ignore[return-value]
