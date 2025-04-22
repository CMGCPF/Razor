import asyncio
import discord
from discord.ext import commands
import logging
import json
import os
from colorama import Fore, Style, init as colorama_init
from config import INVENTORY_DIR, PLAYER_DATA
from utils.PlayerDataRequest import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


class VoirVoitureSelect(discord.ui.Select):
    def __init__(self, voiture_data):
        options = [
            discord.SelectOption(label=voiture["nom"], value=nom, emoji="<:crvt:1345789789160607875>") for nom, voiture in voiture_data.items()
        ]
        super().__init__(placeholder="Voir une voiture", options=options)
        self.voiture_data = voiture_data

    async def callback(self, interaction: discord.Interaction):
        voiture = self.voiture_data[self.values[0]]
        embed = discord.Embed(title=f"{voiture['nom']}", color=discord.Color.blue())
        embed.set_image(url=voiture["image_url"])
        embed.add_field(name="Prix", value=f"`{voiture['prix']}` bounds", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Inventaire(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")

    @commands.hybrid_command(name='inventaire', with_app_command=True,
                             description="Affiche l'inventaire du membre choisi.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def inventaire(self, ctx, membre: discord.Member = None):
        membre = membre or ctx.author
        user_inventory_path = os.path.join(INVENTORY_DIR, str(membre.id))

        player_data_path = PLAYER_DATA
        if os.path.exists(player_data_path):
            with open(player_data_path, "r", encoding="utf-8") as f:
                player_data = json.load(f)
        else:
            player_data = {}

        bounds = player_data.get(str(membre.id), {}).get("bounds", 0)

        if not os.path.exists(user_inventory_path):
            return await ctx.send(f"**{membre.display_name}** ne possède aucun garage.", ephemeral=True)

        voiture_files = [f for f in os.listdir(user_inventory_path) if f.startswith("voiture-") and f.endswith(".json")]
        if not voiture_files:
            return await ctx.send(f"**{membre.display_name}** ne possède aucune voiture.", ephemeral=True)

        voiture_data = {}
        voiture_list_text = ""

        for file_name in sorted(voiture_files):
            file_path = os.path.join(user_inventory_path, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    voiture_data[data["nom"]] = data
                    voiture_list_text += f"{data['nom']} : `{data['prix']}` bounds\n"
            except Exception as e:
                logger.error(f"Erreur lors de la lecture de {file_name} : {e}")

        embed = discord.Embed(title=f"Inventaire de {membre.display_name}", color=discord.Color.light_embed())
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name=f"Nombre de bounds : {bounds}", value=" ", inline=False)
        embed.add_field(name=f"Nombre de voitures : {len(voiture_files)}", value=" ", inline=False)
        embed.add_field(name="Liste des voitures \n", value=voiture_list_text, inline=False)

        view = discord.ui.View()
        view.add_item(VoirVoitureSelect(voiture_data))

        await ctx.send(embed=embed, view=view)

    @inventaire.error
    async def inventaire_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"Attendez encore **{time_left}** seconde(s) avant de réutiliser cette commande.",
                           ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Inventaire(bot))
