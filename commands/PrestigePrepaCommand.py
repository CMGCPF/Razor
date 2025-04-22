import asyncio
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

import logging
import json
import os

from colorama import Fore, Style
from colorama import init as colorama_init

from events.PrestigePrepa import PREPA_DATA, prepa_role

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


def load_json(file_path):
    return json.load(open(file_path, "r")) if os.path.exists(file_path) else {}


def save_json(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


class PrestigePrepaCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

    @commands.hybrid_command(name="prepa", with_app_command=True, description="Gérer les commandes de préparation automobile")
    @app_commands.describe(
        commande="Numéro de commande",
        action="Action à effectuer",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Finir", value="cancel"),
        ]
    )
    @commands.has_role(prepa_role)
    async def prepa(self, ctx, commande: int, action: str):
        global preparation_message
        try:
            preparation_message = await ctx.send("**Préparation en cours...** Veuillez patienter.", ephemeral=True)

            data = load_json(PREPA_DATA)

            order_key = None
            for key, value in data.items():
                if value.get("order_number") == commande:
                    order_key = key
                    break

            if order_key is None:
                await preparation_message.edit(content=f"❌ Commande {commande} introuvable.", embed=None, ephemeral=True)
                return

            order_data = data[order_key]
            channel_id = order_data["channel_id"]
            message_id = order_data["message_id"]

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await preparation_message.edit(content="❌ Salon de la commande introuvable.", embed=None, ephemeral=True)
                return

            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                await preparation_message.edit(content="❌ Message de la commande introuvable.", embed=None, ephemeral=True)
                return

            if action == "cancel":
                del data[order_key]
                save_json(data, PREPA_DATA)

                await channel.delete()

        except discord.errors.NotFound as e:
            logger.error(f"Erreur : {e}")
            await preparation_message.edit(content="❌ Une erreur est survenue, le message ou le canal est introuvable.",
                                           embed=None, ephemeral=True)
        except discord.errors.HTTPException as e:
            logger.error(f"Erreur HTTP : {e}")
            await preparation_message.edit(
                content="❌ Une erreur HTTP est survenue, vérifiez les permissions ou la validité du canal.", embed=None, ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur inconnue : {e}")
            await preparation_message.edit(content="❌ Une erreur inattendue est survenue.", embed=None, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PrestigePrepaCommand(bot))
