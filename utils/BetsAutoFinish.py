import logging
import json
import os
import discord
import asyncio
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from colorama import Fore, Style, init as colorama_init
from utils.PlayerDataRequest import load_bets, save_bets
from config import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


async def check_pari_active(self):
    logger.debug('Initialisation de check_pari_active')
    bets = load_bets()
    now = datetime.utcnow()

    for channel_id, bet in list(bets.items()):
        bet_time = datetime.fromisoformat(bet["date"])
        if now - bet_time > timedelta(hours=24):
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                await channel.delete()
                print(f"{channel_id} à été supprimé !")
            bets.pop(str(channel_id), None)
            save_bets(bets)
