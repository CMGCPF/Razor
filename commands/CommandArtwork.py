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

from events.RacingArtwork import artwork_role, ARTWORK_DATA

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


green_b1 = "<:bG21:1351288397154750624>"
green_c1 = "<:gC2:1351288423855423639>"
green_b2 = "<:bG20:1351288371695325214>"

red_c2 = "<:gC1:1351288433045274724>"
red_b3 = "<:gB10:1351288381618913411>"
red_b2 = "<:gB11:1351288406566506496>"


def generate_progress_bar(progress: int):
    full_blocks = progress // 10
    empty_blocks = 10 - full_blocks

    if progress == 0:
        return f"{red_b2}{red_c2 * empty_blocks}{red_b3}"
    elif progress == 100:
        return f"{green_b1}{green_c1 * full_blocks}{green_b2}"
    else:
        return f"{green_b1}{green_c1 * full_blocks}{red_c2 * empty_blocks}{red_b3}"


class CommandArtwork(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

    @commands.hybrid_command(name="artwork", with_app_command=True, description="Gérer les commandes de custom")
    @app_commands.describe(
        commande="Numéro de commande",
        action="Action à effectuer",
        pourcentage="Progression (0-100%) si applicable"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Commencer", value="start"),
            app_commands.Choice(name="Finir", value="cancel"),
        ]
    )
    @commands.has_role(artwork_role)
    async def artwork(self, ctx, commande: int, action: str, pourcentage: int = None):
        global preparation_message
        try:
            preparation_message = await ctx.send("**Préparation en cours...** Veuillez patienter.")

            data = load_json(ARTWORK_DATA)

            order_key = None
            for key, value in data.items():
                if value.get("order_number") == commande:
                    order_key = key
                    break

            if order_key is None:
                await preparation_message.edit(content=f"❌ Commande {commande} introuvable.", embed=None)
                return

            order_data = data[order_key]
            channel_id = order_data["channel_id"]
            message_id = order_data["message_id"]

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await preparation_message.edit(content="❌ Salon de la commande introuvable.", embed=None)
                return

            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                await preparation_message.edit(content="❌ Message de la commande introuvable.", embed=None)
                return

            if action == "start":
                if pourcentage is None or not (0 <= pourcentage <= 100):
                    await preparation_message.edit(content="❌ Veuillez fournir un pourcentage valide (0-100%).",
                                                   embed=None)
                    return

                embed = message.embeds[0]
                progress_bar = generate_progress_bar(pourcentage)

                existing_field_index = None
                for i, field in enumerate(embed.fields):
                    if "Progression" in field.name:
                        existing_field_index = i
                        break

                if existing_field_index is not None:
                    embed.remove_field(existing_field_index)

                embed.add_field(name="Progression", value=f"`{pourcentage} %`\n{progress_bar}", inline=False)

                await message.edit(embed=embed)
                await preparation_message.edit(
                    content=f"✔️ Progression mise à jour pour la commande #{commande} : {pourcentage}%.", embed=None)

            elif action == "cancel":
                del data[order_key]
                save_json(data, ARTWORK_DATA)

                await channel.delete()

        except discord.errors.NotFound as e:
            logger.error(f"Erreur : {e}")
            await preparation_message.edit(content="❌ Une erreur est survenue, le message ou le canal est introuvable.",
                                           embed=None)
        except discord.errors.HTTPException as e:
            logger.error(f"Erreur HTTP : {e}")
            await preparation_message.edit(
                content="❌ Une erreur HTTP est survenue, vérifiez les permissions ou la validité du canal.", embed=None)
        except Exception as e:
            logger.error(f"Erreur inconnue : {e}")
            await preparation_message.edit(content="❌ Une erreur inattendue est survenue.", embed=None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommandArtwork(bot))
