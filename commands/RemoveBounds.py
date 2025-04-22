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


class RemoveBounds(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")

    @commands.hybrid_group(name='retirer', with_app_command=True,
                           description='Retirer des bounds')
    async def retirer(self, ctx):
        pass

    @retirer.command(name='bounds', with_app_command=True,
                     description='Retirer des bounds à un membre',
                     aliases=['remove', 'rm', 'supprimer', 'delete'])
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def remove_bounds(self, ctx, member: discord.Member, amount: int):
        self.player_data = load_player_data()
        user_id = str(member.id)

        if user_id not in self.player_data:
            self.player_data[user_id] = {"username": member.name, "bounds": 0}

        old_balance = self.player_data[user_id]["bounds"]
        new_balance = max(0, old_balance - amount)

        self.player_data[user_id]["bounds"] = new_balance

        save_player_data(self.player_data)

        embed = discord.Embed(
            title="Bounds retirés",
            description=f"`{amount}` bounds ont été retirés à {member.mention} !\n\n"
                        f"**Nouveau solde :** `{new_balance}` bounds",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

        logger.info(
            f"{Fore.YELLOW}{ctx.author} a retiré {amount} bounds à : {Fore.CYAN}{member} | Nouveau solde : {new_balance}{Style.RESET_ALL}"
        )

        del self.player_data[user_id]

        transactions = load_transactions()
        timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
        transactions.setdefault(str(member.id), []).append({
            "action": f"**-{amount}** <:bounds_c:1346948316193357917> | Retrait par {ctx.author.name}",
            "date": f"<t:{timestamp}:R>"
        })
        save_transactions(transactions)

    @remove_bounds.error
    async def remove_bounds_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("**Vous n'avez pas la permission d'exécuter cette commande.**", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"**Vous devez attendre encore **{time_left}** seconde(s).**", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("**Usage : `/retirer bounds @membre montant`**", ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("**Merci de mentionner un membre valide et d'entrer un montant numérique.**", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RemoveBounds(bot))
