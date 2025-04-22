import logging
import json
import os
from datetime import datetime

import pytz
from colorama import Fore, Style
from colorama import init as colorama_init

import discord
from discord.ext import commands

from utils.PlayerDataRequest import *
from config import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


class AddBounds(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

    @commands.hybrid_group(name='ajouter', with_app_command=True,
                           description='Ajouter des bounds')
    async def nouveau(self, ctx):
        pass

    @nouveau.command(name='bounds', with_app_command=True,
                     description='Ajouter des bounds à un membre',
                     aliases=['money', 'new', 'add', 'add-bounds'])
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def add_bounds(self, ctx, member: discord.Member, amount: int):
        self.player_data = load_player_data()
        user_id = str(member.id)

        if user_id not in self.player_data:
            self.player_data[user_id] = {"username": member.name, "bounds": 0}

        self.player_data[user_id]["bounds"] += amount

        save_player_data(self.player_data)

        embed = discord.Embed(title="Bounds ajoutés",
                              description=f"`{amount}` bounds ont été ajoutés à {member.mention} !\n\nTotal actuel: {self.player_data[user_id]['bounds']} bounds",
                              color=discord.Color.light_embed())
        await ctx.send(embed=embed)

        logger.info(
            f"{Fore.YELLOW}{ctx.author} a ajouté {amount} bounds à : {Fore.CYAN}{member} | Total: {self.player_data[user_id]['bounds']}{Style.RESET_ALL}")

        del self.player_data[user_id]

        transactions = load_transactions()
        timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
        transactions.setdefault(str(member.id), []).append({
            "action": f"**+{amount}** <:bounds_b:1346948303887274005> | Ajouté par {ctx.author.name}",
            "date": f"<t:{timestamp}:R>"
        })
        save_transactions(transactions)

    @add_bounds.error
    async def add_bounds_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("**Vous n'avez pas la permission d'exécuter cette commande.**", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"**Vous devez attendre encore **{time_left}** seconde(s).**", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("**Usage : `/ajouter bounds @membre montant`**", ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("**Merci de mentionner un membre valide et d'entrer un montant numérique.**", ephemeral=True)


def fix_json_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        with open(filename, "r", encoding="utf-8") as file:
            content = file.read()
            content = content.strip()
            if not content.endswith("}"):
                content += "}"
            data = json.loads(content)

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        logger.info(f"Fichier {filename} réparé avec succès.")


fix_json_file(PLAYER_DATA)
fix_json_file(TRANSACTION_FILE)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AddBounds(bot))
