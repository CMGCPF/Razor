import logging
import json
import os
import discord
import asyncio
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from colorama import Fore, Style, init as colorama_init
from utils.PlayerDataRequest import *
from utils.LeaderBoard import update_leaderboard
from utils.BetsAutoFinish import check_pari_active
from utils.HebdoDrop import check_hebdo_drop
from config import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


async def load_player_data():
    return await asyncio.to_thread(load_data, PLAYER_DATA)


class MinutesTasks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.player_data = {}
        self.task_loop.start()

    def cog_unload(self):
        self.task_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}L'événement : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")
        if not self.task_loop.is_running():
            self.task_loop.start()

    @commands.Cog.listener()
    async def on_resumed(self):
        if not self.task_loop.is_running():
            self.task_loop.restart()

    @tasks.loop(minutes=1)
    async def task_loop(self):
        try:
            self.player_data = await load_player_data()
            await update_leaderboard(self)
            await check_pari_active(self)
            await asyncio.create_task(check_hebdo_drop(self))
        except Exception as e:
            logger.error(f"Erreur dans la tâche récurrente : {e}")

    @task_loop.before_loop
    async def before_task_loop(self):
        await self.bot.wait_until_ready()
        self.player_data = await load_player_data()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MinutesTasks(bot))
