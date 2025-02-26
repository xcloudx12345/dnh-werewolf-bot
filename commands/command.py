from commands import admin, player
import commands
import config
from game import text_template

import discord
import asyncio   # Do not remove this. This for debug command
import re
from datetime import *
import tzlocal
import subprocess
import os
from dateutil import parser, tz

import utils

# TODO: generate content of command embed_data
# e.g: Select a player to vote/kill/... by using command ...\nFor example: ...


def parse_time_str(time_str):
    args_matches = re.findall(r"^([+-])*(\d{1,2}|\d{1,2}:?\d{2})$", time_str)
    if len(args_matches):
        args_matches = args_matches[0]
        args_tz_sign = "+" if args_matches[0].count("-") % 2 == 0 else "-"
        args_tz_parts = args_matches[1].split(":")
        if len(args_tz_parts) == 2:  # \d+:\d+
            return args_tz_sign, args_tz_parts[0], args_tz_parts[1]
        elif len(args_tz_parts[0]) <= 2:  # \d | \d\d
            return args_tz_sign, args_tz_parts[0], 0
        elif len(args_tz_parts[0]) <= 4:  # (\d)(\d\d) | (\d\d)(\d\d)
            return args_tz_sign, args_tz_parts[0][:-2], args_tz_parts[0][-2:]

    return None


async def parse_command(client, game, message):
    message_parts = message.content.strip()[len(config.BOT_PREFIX):].split(" ")
    cmd, parameters = message_parts[0], message_parts[1:]
    # Game commands only valid under GAME CATEGORY:
    if admin.is_valid_category(message):
        if cmd == "help":
            await admin.send_embed_to_channel(
                message.guild, text_template.generate_help_text(*parameters), message.channel.name, False
            )
        elif cmd == "version":
            tag = subprocess.check_output(["git", "describe", "--tags"]).decode('utf-8')  # git describe --tags
            name = os.getenv("BOT_NAME")
            await message.reply(f"{name}-{tag}".rstrip('\n'))  # prevent bug of name's or tag's type
        elif cmd == "join":
            await player.do_join(game, message, force=False)
        elif cmd == "leave":
            await player.do_leave(game, message, force=False)
        elif cmd == "watch":
            await player.do_watch(game, message)
        elif cmd == "unwatch":
            await player.do_unwatch(game, message)
        elif cmd == "start":
            await player.do_start(game, message, force=False)
        elif cmd == "next":  # Next phase
            await player.do_next(game, message, force=False)
        elif cmd == "stopgame":
            await player.do_stop(game, message, force=False)

        elif cmd in ("vote", "kill", "guard", "seer", "reborn", "curse", "zombie", "ship"):
            if not game.is_started():
                # prevent user uses command before game starts
                await message.reply(text_template.generate_game_not_started_text())
                return None

            if not game.is_in_play_time():
                await message.reply(text_template.generate_game_not_playing_text())
                return None

            is_valid_channel = \
                (cmd == "vote" and message.channel.name == config.GAMEPLAY_CHANNEL) or\
                (cmd == "kill" and message.channel.name == config.WEREWOLF_CHANNEL) or\
                (cmd in ("guard", "seer", "reborn", "curse", "zombie", "ship")
                 and message.channel.name.strip().startswith("personal"))

            if is_valid_channel:
                author = message.author
                required_param_number = commands.get_command_param_number(cmd)

                if len(message.raw_mentions) == required_param_number:
                    msg = await game.do_player_action(cmd, author.id, *message.raw_mentions)
                    await message.reply(msg)

                elif len(parameters) == required_param_number:
                    is_valid_command = False
                    if all(param.isdigit() for param in parameters):
                        targets_index = [int(param) - 1 for param in parameters]
                        id_players = game.get_dead_players() if cmd == "reborn" else game.get_alive_players()
                        if all(0 <= i < len(id_players) for i in targets_index):
                            is_valid_command = True
                            msg = await game.do_player_action(cmd, author.id, *[id_players[i].player_id for i in targets_index])
                            await message.reply(msg)
                        else:
                            await message.reply(text_template.generate_invalid_command_text(cmd))

                    if not is_valid_command:
                        await message.reply(text_template.generate_invalid_command_text(cmd))
                else:
                    await message.reply(text_template.generate_not_vote_n_player_text(required_param_number))
            else:
                if cmd == "vote":
                    real_channel = f"#{config.GAMEPLAY_CHANNEL}"
                elif cmd == "kill":
                    real_channel = f"#{config.WEREWOLF_CHANNEL}"
                else:
                    real_channel = "riêng của bạn"

                await admin.send_text_to_channel(
                    message.guild, text_template.generate_invalid_channel_text(real_channel), message.channel.name
                )

        elif cmd == "status":
            # status_description, remaining_time, vote_table, vote_table_description = game.get_game_status(message.channel.name, message.author.id)
            # await player.do_generate_vote_status_table(message.channel, vote_table, vote_table_description)
            # await message.reply(text_template.generate_timer_remaining_text(game.timecounter))

            # new status table here
            game_status = game.get_game_status(message.channel.name, message.author.id)
            await player.do_generate_status_table(message.channel, *game_status)

        elif cmd == "timer":
            """ Usage: 
                `!timer 60 30 20` -> dayphase=60s, nightphase=30s, alertperiod=20s
            """
            if len(parameters) < 3:
                timer_phase = [config.DAYTIME, config.NIGHTTIME, config.ALERT_PERIOD]
                await message.reply(
                    "Use default settings: " +
                    f"dayphase={config.DAYTIME}s, nightphase={config.NIGHTTIME}s, alertperiod={config.ALERT_PERIOD}s"
                )
            else:
                timer_phase = list(map(int, parameters))
                # Check if any timer phase is too short (<= 5 seconds):
                if not timer_phase or any(map(lambda x: x <= 5, timer_phase)):
                    await message.reply("Config must greater than 5s")
                    return None
                await message.reply(
                    "New settings: " +
                    f"dayphase={timer_phase[0]}s, nightphase={timer_phase[1]}s, alertperiod={timer_phase[2]}s"
                )
            game.set_timer_phase(timer_phase)

        elif cmd == "timerstart":
            game.timer_stopped = False
            await message.reply(text_template.generate_timer_start_text())
        elif cmd == "timerstop":
            game.timer_stopped = True
            await message.reply(text_template.generate_timer_stop_text())

        elif cmd == "setplaytime":
            """Usage:
                `!setplaytime 10:00 21:00 UTC+7` -> start_time = 10:00, end_time = 21:00, zone=UTC+7
            """
            if len(parameters) >= 2:
                zone = "UTC+7"
                if len(parameters) >= 3:
                    zone = parameters[2]

                try:
                    if zone:
                        preprocessed_zone = re.sub(r"(?:GMT|UTC)([+-]\d+)", r"\1", zone)
                        start_time = parser.parse(f"{parameters[0]} {preprocessed_zone}")
                        end_time = parser.parse(f"{parameters[1]} {preprocessed_zone}")
                    else:
                        start_time = parser.parse(f"{parameters[0]}")
                        end_time = parser.parse(f"{parameters[1]}")

                except parser.ParserError:
                    await message.reply(text_template.generate_invalid_command_text(cmd))
                    start_time = None
                    end_time = None

                if start_time is not None and end_time is not None:
                    start_time_utc = start_time.astimezone(tz.UTC)
                    end_time_utc = end_time.astimezone(tz.UTC)
                    game.set_play_time(start_time_utc.time(), end_time_utc.time(), zone)
                    msg = text_template.generate_play_time_text(start_time_utc.time(), end_time_utc.time(), zone)
                    await message.reply(msg)

        elif cmd == "setroles":
            res = game.add_default_roles(parameters)
            await message.reply(res)
        elif cmd == "showmodes":
            modes = utils.common.read_json_file("json/game_config.json")
            await message.reply(text_template.generate_modes(modes))
        elif cmd == "setmode":
            mode = parameters[0]
            on = True if parameters[1] == 'on' else False
            res = game.set_mode(mode, on)
            await message.reply(res)

        elif cmd.startswith('f'):
            if admin.is_admin(message.author):
                if cmd == "fjoin":
                    await admin.create_channel(message.guild, client.user, config.GAMEPLAY_CHANNEL, is_public=False)
                    await player.do_join(game, message, force=True)
                elif cmd == "fleave":
                    await player.do_leave(game, message, force=True)
                elif cmd == "fstart":
                    await player.do_start(game, message, force=True)
                elif cmd == "fnext":  # Next phase
                    await player.do_next(game, message, force=True)
                elif cmd == "fstopgame":
                    await player.do_stop(game, message, force=True)
                elif cmd == "fclean":  # Delete all private channels under config.GAME_CATEGORY
                    try:
                        await admin.delete_channel(message.guild, client.user, config.GAMEPLAY_CHANNEL)
                        await admin.delete_channel(message.guild, client.user, config.WEREWOLF_CHANNEL)
                        await admin.delete_channel(message.guild, client.user, config.CEMETERY_CHANNEL)
                        await admin.delete_channel(message.guild, client.user, config.COUPLE_CHANNEL)
                        await admin.delete_all_personal_channel(message.guild)
                        await admin.create_channel(message.guild, client.user, config.GAMEPLAY_CHANNEL, is_public=False)
                    except Exception as e:
                        print(e)
                elif cmd == "fdebug":
                    # print(asyncio.all_tasks())
                    exec(" ".join(parameters))
            else:
                await message.reply("You do not have Admin role.")

    # Admin/Bot commands - User should not directly use these commands
    if cmd.startswith('f'):
        if admin.is_admin(message.author):
            if cmd == "fcreate":  # Create game channels
                if len(message.mentions) == 1:
                    user = message.mentions[0]
                    if user.id == client.user.id:
                        await admin.create_category(message.guild, client.user, config.GAME_CATEGORY)
                        await admin.create_channel(message.guild, client.user, config.LOBBY_CHANNEL, is_public=True)
                        await admin.create_channel(message.guild, client.user, config.GAMEPLAY_CHANNEL, is_public=False)
                        await admin.create_channel(message.guild, client.user, config.LEADERBOARD_CHANNEL, is_public=True, is_admin_writeonly=True)
                else:
                    await message.reply("Missing @bot_name")
            elif cmd == "fdelete":  # Delete all channels and category under config.GAME_CATEGORY
                if len(message.mentions) == 1:
                    user = message.mentions[0]
                    try:
                        if user.id == client.user.id:
                            await admin.delete_channel(message.guild, client.user, config.GAMEPLAY_CHANNEL)
                            await admin.delete_channel(message.guild, client.user, config.WEREWOLF_CHANNEL)
                            await admin.delete_channel(message.guild, client.user, config.CEMETERY_CHANNEL)
                            await admin.delete_all_personal_channel(message.guild)
                            await admin.delete_channel(message.guild, client.user, config.LOBBY_CHANNEL)
                            await admin.delete_category(message.guild, client.user)
                    except Exception as e:
                        print(e)
                else:
                    await message.reply("Missing @bot_name")
        else:  # No need to reply because there are many bots
            pass


async def test_commands(guild):
    print("Testing admin command")
    if not isinstance(guild, discord.Guild):
        raise AssertionError

    # List all users:
    admin.list_users(guild)

    # Test player commands
    await player.test_player_command(guild)

    # Test admin commands
    await admin.test_admin_command(guild)
