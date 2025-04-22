import json
import logging
import os
from datetime import datetime, timezone, timedelta

import discord
import pytz
from colorama import Fore, Style
from colorama import init as colorama_init
from discord import ui
from discord.ext import commands

from config import *
from utils.PlayerDataRequest import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)

os.makedirs(HEBDO_DROP_DIR, exist_ok=True)
os.makedirs(INVENTORY_DIR, exist_ok=True)

if os.path.exists(BUTTON_FILE):
    with open(BUTTON_FILE, "r", encoding="utf-8") as f:
        buttons_state = json.load(f)
else:
    buttons_state = {}


class HebdoDropForm(ui.Modal, title="Créer un HebdoDrop"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    nom = ui.TextInput(label="Nom du véhicule", placeholder="Ex: BMW M3 GTR")
    prix = ui.TextInput(label="Prix en bounds", placeholder="Ex: 5000")
    date_renvoi = ui.TextInput(label="Date du drop", placeholder="Ex: 10-03-2025")
    image_url = ui.TextInput(label="URL de l'image", placeholder="Ex: https://exemple.com/image.png")

    async def on_submit(self, interaction: discord.Interaction):
        drop_path = os.path.join(HEBDO_DROP_DIR, "hebdo_drop.json")

        try:
            with open(drop_path, "r", encoding="utf-8") as f:
                drops = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            drops = {}

        try:
            drop_date = datetime.strptime(self.date_renvoi.value, "%d-%m-%Y")
            drop_datetime = drop_date.replace(hour=21, minute=13, second=0)
            paris_tz = timezone(timedelta(hours=1))
            drop_datetime = drop_datetime.replace(tzinfo=paris_tz)
            drop_timestamp = int(drop_datetime.timestamp())
            drop_timestamp_str = f"<t:{drop_timestamp}:R>"
        except ValueError:
            await interaction.response.send_message("Format de date invalide. Utilisez dd-MM-YYYY.", ephemeral=True)
            return

        annonce_channel = interaction.guild.get_channel(1327980406049603584)
        if annonce_channel:
            annonce_embed = discord.Embed(
                title="Un Drop Arrive Bientôt !",
                description=f"**Date** : {drop_timestamp_str}\n"
                            f"Préparez vos bounds, un véhicule rare arrivera ici sous peu !",
                color=discord.Color.dark_embed()
            )
            annonce_message = await annonce_channel.send(embed=annonce_embed)

            drop_data = {
                "nom": self.nom.value,
                "prix": self.prix.value,
                "date": self.date_renvoi.value,
                "timestamp": drop_timestamp,
                "image_url": self.image_url.value,
                "achete": False,
                "acheteur": None
            }

            drops[str(annonce_message.id)] = drop_data

            buttons_state[str(annonce_message.id)] = {
                "channel_id": annonce_channel.id,
                "active": True,
            }

            with open(drop_path, "w", encoding="utf-8") as f:
                json.dump(drops, f, indent=4)

            with open(BUTTON_FILE, "w", encoding="utf-8") as f:
                json.dump(buttons_state, f, indent=4)

            save_buttons_state()

        await interaction.response.send_message("Le HebdoDrop a été enregistré avec succès !", ephemeral=True)


class ConfirmPurchaseView(ui.View):
    def __init__(self, drop_data, embed_id, interaction_user):
        super().__init__(timeout=None)
        self.drop_data = drop_data
        self.embed_id = embed_id
        self.interaction_user_id = interaction_user.id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("Tu ne peux pas confirmer l'achat d'un autre joueur !",
                                                    ephemeral=True)
            return

        player_data = load_player_data()
        user_id = str(interaction.user.id)

        drop_price = int(self.drop_data["prix"].replace(" ", ""))
        if user_id in player_data and player_data[user_id]["bounds"] >= drop_price:
            player_data[user_id]["bounds"] -= drop_price
            save_player_data(player_data)

            drop_path = os.path.join(HEBDO_DROP_DIR, "hebdo_drop.json")

            with open(drop_path, "r", encoding="utf-8") as f:
                drops = json.load(f)

            if drops[self.embed_id]["achete"]:
                await interaction.response.send_message(
                    "Désolé, cette voiture a déjà été achetée par un autre joueur !", ephemeral=True)
                return

            drops[self.embed_id]["achete"] = True
            drops[self.embed_id]["acheteur"] = user_id

            with open(drop_path, "w", encoding="utf-8") as f:
                json.dump(drops, f, indent=4)

            user_inventory_dir = os.path.join(INVENTORY_DIR, user_id)
            os.makedirs(user_inventory_dir, exist_ok=True)
            existing_files = [f for f in os.listdir(user_inventory_dir) if
                              f.startswith("voiture-") and f.endswith(".json")]
            new_index = len(existing_files) + 1
            voiture_path = os.path.join(user_inventory_dir, f"voiture-{new_index}.json")

            with open(voiture_path, "w", encoding="utf-8") as f:
                json.dump({
                    "nom": self.drop_data["nom"],
                    "prix": self.drop_data["prix"],
                    "image_url": self.drop_data["image_url"]
                }, f, indent=4)

            transactions = load_transactions()
            timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
            transactions.setdefault(user_id, []).append({
                "action": f"**-{self.drop_data['prix']}** <:bounds_c:1346948316193357917> | Achat de `{self.drop_data['nom']}`",
                "date": f"<t:{timestamp}:R>"
            })
            save_transactions(transactions)

            await interaction.response.send_message(
                f"Félicitations ! Tu as acheté **{self.drop_data['nom']} pour {self.drop_data['prix']}**.\nIl te "
                f"reste **{player_data[user_id]['bounds']}** bounds.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Tu n'as pas assez de bounds pour cet achat !", ephemeral=True)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("Tu ne peux pas annuler l'achat d'un autre joueur !",
                                                    ephemeral=True)
            return
        await interaction.response.send_message("Achat annulé.", ephemeral=True)


class HebdoDropView(ui.View):
    def __init__(self, message_id: str, custom_id: str = "hebdo_drop_view"):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.custom_id = custom_id

    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.success, custom_id="buy_drop_unique")
    async def buy_drop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player_data = load_player_data()
        user_id = str(interaction.user.id)
        drop_path = os.path.join(HEBDO_DROP_DIR, "hebdo_drop.json")

        if not os.path.exists(drop_path):
            await interaction.response.send_message("Aucun drop disponible.", ephemeral=True)
            return

        with open(drop_path, "r", encoding="utf-8") as f:
            drops = json.load(f)

        embed_id = str(interaction.message.id)

        if embed_id not in drops:
            await interaction.response.send_message("Ce drop n'est plus disponible.", ephemeral=True)
            return

        drop_data = drops[embed_id]

        if drop_data["achete"]:
            await interaction.response.send_message("Ce drop a déjà été acheté par quelqu'un d'autre.", ephemeral=True)
            return

        drop_price = int(drop_data["prix"].replace(" ", ""))

        if user_id in player_data and player_data[user_id]["bounds"] >= drop_price:
            view = ConfirmPurchaseView(drop_data, embed_id, interaction.user)

            embed = discord.Embed(
                title="Confirme ton achat",
                description=f"Veux-tu acheter **{drop_data['nom']}** pour **{drop_data['prix']}** bounds ?",
                color=discord.Color.light_embed()
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Tu n'as pas assez de bounds pour cet achat !", ephemeral=True)


def save_buttons_state():
    logger.debug(f"Avant sauvegarde de l'état des boutons: {buttons_state}")

    with open(BUTTON_FILE, "w", encoding="utf-8") as f:
        json.dump(buttons_state, f, indent=4)

    logger.debug(f"Après sauvegarde de l'état des boutons: {buttons_state}")


async def restore_buttons(bot):
    if not buttons_state:
        return

    logger.info(f"{Fore.CYAN}Chargement des boutons enregistrés...{Style.RESET_ALL}")

    for message_id, state in list(buttons_state.items()):
        if not isinstance(state, dict):
            logger.warning(
                f"L'état du bouton pour le message {message_id} n'est pas un dictionnaire. Correction en cours...")
            del buttons_state[message_id]
            save_buttons_state()
            continue

        channel_id = 1327980406049603584
        channel = bot.get_channel(channel_id)

        if channel:
            try:
                message = await channel.fetch_message(int(message_id))

                view = HebdoDropView(message_id=str(message_id))

                drop_path = os.path.join(HEBDO_DROP_DIR, "hebdo_drop.json")
                with open(drop_path, "r", encoding="utf-8") as f:
                    drops = json.load(f)

                drop_data = drops.get(str(message_id))
                if drop_data and drop_data["achete"]:
                    for button in view.children:
                        button.disabled = True

                await message.edit(view=view)

                logger.info(
                    f"{Fore.GREEN}Bouton restauré :{Style.RESET_ALL} Message ID {message_id} dans le canal (ID: {channel.id})"
                )

            except discord.NotFound:
                logger.warning(
                    f"{Fore.RED}Message ID {message_id} introuvable dans le canal {channel.id}.{Style.RESET_ALL}")
            except discord.Forbidden:
                logger.warning(
                    f"{Fore.RED}Accès refusé au canal ID {channel.id}, impossible de restaurer le bouton.{Style.RESET_ALL}")
            except Exception as e:
                logger.error(
                    f"{Fore.RED}Erreur lors de la restauration du bouton ID {message_id} : {e}{Style.RESET_ALL}")


async def update_hebdo_views(bot):
    drop_path = os.path.join(HEBDO_DROP_DIR, "hebdo_drop.json")

    if not os.path.exists(drop_path):
        return

    with open(drop_path, "r", encoding="utf-8") as f:
        drops = json.load(f)

    for message_id, state in buttons_state.items():
        if not isinstance(state, dict):
            logger.warning(f"L'état du bouton pour le message {message_id} n'est pas un dictionnaire. Ignoré.")
            continue

        channel_id = state.get("channel_id")
        if not channel_id:
            continue

        channel = bot.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(int(message_id))
                if drops.get(str(message_id), {}).get("achete"):
                    view = HebdoDropView(message_id=str(message_id))
                    for button in view.children:
                        button.disabled = True
                else:
                    view = HebdoDropView(message_id=str(message_id))

                await message.edit(view=view)
                logger.info(f"View mise à jour pour le message {message_id}")
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour du view pour {message_id} : {e}")


class HebdoDropCommandView(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Créer un HebdoDrop", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HebdoDropForm(self.bot))


class HebdoDrop(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.loop.create_task(restore_buttons(bot))
        self.bot.loop.create_task(update_hebdo_views(bot))

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")

        await restore_buttons(self.bot)

    @commands.hybrid_command(name='hebdodrop', with_app_command=True,
                             description='Créer un nouvel hebdodrop',
                             aliases=['drop', 'hebdo'])
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def HebdoDrop(self, ctx):
        view = HebdoDropCommandView(self.bot)

        embed = discord.Embed(title="Aide HebdoDrop",
                              description=f"Si vous ne savez pas comment obtenir l'URL de votre image, envoyez-la "
                                          f"dans un salon privé et copiez son URL. \n\nElle devrait ressembler à ceci "
                                          f":\n`https://cdn.discordapp.com/attachments/123456789"
                                          f"/123456789/image.png?ex=1234`",
                              color=discord.Color.light_embed())

        message = await ctx.send(embed=embed, view=view, ephemeral=True)
        buttons_state[str(message.id)] = ctx.channel.id
        save_buttons_state()

        logger.info(f"{Fore.YELLOW}La commande hebdodrop a été utilisée par : {Fore.CYAN}{ctx.author}{Style.RESET_ALL}")

    @HebdoDrop.error
    async def HebdoDrop_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("**Vous n'avez pas la permission d'exécuter cette commande.**", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"**Vous devez attendre encore **{time_left}** seconde(s).**", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HebdoDrop(bot))
