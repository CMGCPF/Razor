import asyncio
from datetime import datetime, timedelta

import discord
import pytz
from discord.ext import commands
from discord import app_commands

import logging
import json
import os

from colorama import Fore, Style
from colorama import init as colorama_init

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        paris_tz = pytz.timezone("Europe/Paris")
        self.start_time = datetime.now(paris_tz)

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

    @commands.hybrid_command(name='help', with_app_command=True,
                             description='Vous donne les informations sur les fonctionnalitées disponible.',
                             aliases=['aide'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def help(self, ctx):
        paris_tz = pytz.timezone("Europe/Paris")
        timestamp = int(self.start_time.timestamp())

        embed = discord.Embed(title=" Besoin d'aide ? ",
                              description=f"**Voici la liste des commandes disponibles :**\n\n"
                              f"**/pari** [utilisateur] [bounds à parier] [Mode de jeu]\n"
                              f"**↪**Permet de parier avec un utilisateur avec des bounds.\n\n"
                              f"**/inventaire** (utilisateur-optionnel)\n"
                              f"**↪**Permet de voir le garage et les bounds d'un utilisateur.\n\n"
                              f"**/vendre** [Type de ventre]\n"
                              f"**↪**Permet de vendre sa voiture choisi juste apres la commande\n\n"
                              f"**/pari voiture** [utilisateur] [voiture]\n"
                              f"**↪**Permet de parier avec un utilisateur avec des voitures.\n\n\n"
                              f"**Voici la liste des fonctionnalitées disponibles :**\n\n"
                              f"Quand vous choisissez de vendre votre voiture, vous avez le choix entre **Vente "
                                          f"directe** et **Vente publique**. La **Vente directe** permet de vendre "
                                          f"votre voiture immédiatement au prix d'achat, tandis que la **Vente "
                                          f"publique** vous permet de la mettre en vente pour 20 % de plus que son "
                                          f"prix d'origine.\n\n"
                              f"**Uptime :** <t:{timestamp}:R>",

                              color=discord.Color.light_embed())
        await ctx.send(embed=embed, ephemeral=True)

        logger.info(f"{Fore.YELLOW}La commande help a été utilisée par : {Fore.CYAN}{ctx.author}{Style.RESET_ALL}")

    @help.error
    async def help_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"Vous devez attendre encore **{time_left}** seconde(s).", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
