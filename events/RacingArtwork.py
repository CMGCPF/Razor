from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import logging
import pytz

from colorama import init as colorama_init, Fore, Style

from config import PLAYER_DATA
from utils.PlayerDataRequest import load_transactions, save_transactions

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[logging.FileHandler("bot_log.txt"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

timezone = pytz.timezone("Europe/Paris")

ORDER_DATA_FILE = "DATA/JSON/order_data.json"
ARTWORK_CHANNEL = 1347307401442885674
ARTWORK_DATA = "DATA/JSON/artwork_data.json"
ARTWORK_ID_MESSAGE = "DATA/JSON/artwork_id_message.json"
natacha_id = 486104024928616461
artwork_role = 1347305124036350074
CATEGORY = 1309500591776731179


# 486104024928616461

def load_json(file_path):
    return json.load(open(file_path, "r")) if os.path.exists(file_path) else {}


def save_json(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def get_next_order_number():
    data = load_json(ORDER_DATA_FILE)
    data["order_number"] = data.get("order_number", 0) + 1
    save_json(data, ORDER_DATA_FILE)
    return data["order_number"]


class CustomView(discord.ui.View):
    def __init__(self, user, channel, message):
        super().__init__(timeout=None)
        self.user = user
        self.channel = channel
        self.message = message

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != natacha_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        data = load_json(ARTWORK_DATA)
        user_data = data.get(str(self.user.id), {})
        user_data["status"] = "accepted"
        save_json(data, ARTWORK_DATA)

        await interaction.message.edit(view=None)
        await interaction.response.send_message("Commande acceptée !", ephemeral=True)

        view = None
        if user_data.get("custom_type") == "prestige":
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="PayPal de Natacha", url="https://www.paypal.com/paypalme/wendylagoat",
                                  style=discord.ButtonStyle.link))

        embed = self.message.embeds[0]
        await self.message.edit(embed=embed, view=view)

        if user_data.get("custom_type") == "prestige":
            payment_view = PaymentView(self.user, self.channel, self.message)
            payment_embed = discord.Embed(
                title="Confirmation de paiement",
                description="Confirmez-vous que le paiement a bien été effectué ?",
                color=discord.Color.orange()
            )
            await self.channel.send(embed=payment_embed, view=payment_view)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.red)
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != natacha_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        user_id = str(self.user.id)
        data = load_json(ARTWORK_DATA)
        data.pop(user_id, None)
        save_json(data, ARTWORK_DATA)

        player_data = load_json(PLAYER_DATA)
        if user_id in player_data:
            player_data[user_id]["bounds"] += 20000

        natacha_data = player_data.get(str(natacha_id), {"bounds": 0})
        if natacha_data["bounds"] >= 20000:
            natacha_data["bounds"] -= 20000
        else:
            natacha_data["bounds"] = 0

        player_data[str(natacha_id)] = natacha_data
        save_json(player_data, PLAYER_DATA)

        transactions = load_transactions()
        timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
        transactions.setdefault(user_id, []).append({
            "action": f"**+20000** <:bounds_b:1346948303887274005> | Remboursement de la custom refusée par <@{natacha_id}>",
            "date": f"<t:{timestamp}:R>"
        })
        transactions.setdefault(str(natacha_id), []).append({
            "action": f"**-20000** <:bounds_c:1346948316193357917> | Remboursement de la custom refusée de <@{user_id}>",
            "date": f"<t:{timestamp}:R>"
        })
        save_transactions(transactions)

        await self.channel.delete()


class PaymentView(discord.ui.View):
    def __init__(self, user, channel, message):
        super().__init__(timeout=None)
        self.user = user
        self.channel = channel
        self.message = message

    @discord.ui.button(label="✅ Paiement confirmé", style=discord.ButtonStyle.green)
    async def payment_confirmed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != natacha_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        payment_embed = discord.Embed(
            title="Confirmation de paiement",
            description="Le paiement a bien été confirmé. Merci !",
            color=discord.Color.light_embed()
        )

        await interaction.message.edit(embed=payment_embed)
        await interaction.response.send_message("Le paiement a été confirmé !", ephemeral=True)
        await interaction.message.edit(view=None)

    @discord.ui.button(label="❌ Non payé", style=discord.ButtonStyle.red)
    async def payment_refused(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != natacha_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        payment_embed = discord.Embed(
            title="Confirmation de paiement",
            description="Le paiement n'a pas été effectué. Veuillez procéder à l'achat.",
            color=discord.Color.light_embed()
        )

        await interaction.message.edit(embed=payment_embed)
        await interaction.response.send_message("Le paiement n'a pas été effectué.", ephemeral=True)
        await interaction.message.edit(view=PaymentView(self.user, self.channel, self.message))


def format_custom_type(custom_type):
    return {
        "prestige": "Prestige Custom",
        "fast": "Fast Custom"
    }.get(custom_type, custom_type)


async def create_private_channel(guild, user, custom_type, plateforme, vehicule, inspiration):
    data = load_json(ARTWORK_DATA)

    if str(user.id) in data:
        existing_channel_id = data[str(user.id)]["channel_id"]
        existing_channel = guild.get_channel(existing_channel_id)
        if existing_channel:
            return existing_channel

    category = discord.utils.get(guild.categories, id=CATEGORY)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_member(natacha_id): discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = await guild.create_text_channel(f"custom-{user.name}", overwrites=overwrites, category=category)
    order_number = get_next_order_number()

    embed = discord.Embed(
        title=f"Commande #{order_number}",
        description=f"**Type** : {format_custom_type(custom_type)}\n"
                    f"**Utilisateur** : {user.mention}\n\n"
                    f"**Information commande :**\n\n"
                    f"**Plateforme** : {plateforme}\n"
                    f"**Véhicule** : {vehicule}\n"
                    f"**Inspiration** : {inspiration}\n",
        color=discord.Color.light_embed()
    )

    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1333883528768917574/1347857423691415592/l__1_-removebg-preview.png"
    )

    view = CustomView(user, channel, None)
    message = await channel.send(embed=embed, view=view)
    view.message = message

    data[str(user.id)] = {
        "channel_id": channel.id,
        "message_id": message.id,
        "custom_type": custom_type,
        "order_number": order_number,
        "form_data": {
            "plateforme": plateforme,
            "vehicule": vehicule,
            "inspiration": inspiration
        }
    }
    save_json(data, ARTWORK_DATA)

    return channel, message.id


class CustomForm(discord.ui.Modal):
    def __init__(self, bot, user, custom_type):
        super().__init__(title="Racing Artwork by Natacha", timeout=None)
        self.bot = bot
        self.user = user
        self.custom_type = custom_type

        self.plateforme = discord.ui.TextInput(label="Plateforme",
                                               placeholder="Sur quelle plateforme jouez-vous ?",
                                               required=True)
        self.vehicule = discord.ui.TextInput(label="Véhicule",
                                             placeholder="Quel véhicule souhaitez-vous personnaliser ?",
                                             required=True)
        self.inspiration = discord.ui.TextInput(label="Inspiration",
                                                placeholder="Quelles sont vos inspirations et idées pour le custom ?",
                                                required=True)
        self.add_item(self.plateforme)
        self.add_item(self.vehicule)
        self.add_item(self.inspiration)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            plateforme = self.plateforme.value.strip()
            vehicule = self.vehicule.value.strip()
            inspiration = self.inspiration.value.strip()

            if not plateforme or not vehicule or not inspiration:
                await interaction.response.send_message("Veuillez remplir tous les champs du formulaire.",
                                                        ephemeral=True)
                return

            transaction_data = load_json(ORDER_DATA_FILE)
            user_id = str(interaction.user.id)

            now = datetime.now(timezone)
            formatted_time = now.strftime("%d/%m/%Y %H:%M:%S")

            transaction_data[user_id] = {
                "form_data": {
                    "plateforme": plateforme,
                    "vehicule": vehicule,
                    "inspiration": inspiration,
                },
                "date_commande": formatted_time
            }
            save_json(transaction_data, ORDER_DATA_FILE)

            player_data = load_json(PLAYER_DATA)
            user_id = str(self.user.id)
            cost = 20000

            if user_id not in player_data or player_data[user_id]["bounds"] < cost:
                await interaction.response.send_message("❌ Fonds insuffisants !", ephemeral=True)
                return

            player_data[user_id]["bounds"] -= cost
            natacha_data = player_data.get(str(natacha_id), {"bounds": 0})
            natacha_data["bounds"] += cost
            player_data[str(natacha_id)] = natacha_data
            save_json(player_data, PLAYER_DATA)

            transactions = load_transactions()
            timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
            transactions.setdefault(user_id, []).append({
                "action": f"**-20000** <:bounds_c:1346948316193357917> | Achat d'une customisation automobile de <@{natacha_id}>",
                "date": f"<t:{timestamp}:R>"
            })
            transactions.setdefault(natacha_id, []).append({
                "action": f"**+20000** <:bounds_b:1346948303887274005> | Achat d'une customisation automobile de <@{user_id}>",
                "date": f"<t:{timestamp}:R>"
            })
            save_transactions(transactions)

            await create_private_channel(interaction.guild, self.user, self.custom_type,
                                         plateforme, vehicule, inspiration)

            await interaction.response.send_message("Commande confirmée et enregistrée !", ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur lors de la soumission du formulaire : {e}")
            await interaction.response.send_message(
                "❌ Une erreur s'est produite lors du traitement de votre commande. Veuillez réessayer plus tard.",
                ephemeral=True)


class ConfirmTransactionView(discord.ui.View):
    def __init__(self, user, bot, custom_type):
        super().__init__(timeout=None)
        self.user = user
        self.bot = bot
        self.custom_type = custom_type

    @discord.ui.button(label="✅ Oui", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomForm(self.bot, self.user, self.custom_type))

    @discord.ui.button(label="❌ Non", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Commande annulée.", ephemeral=True)


class ArtworkDropdown(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Prestige Custom", value="prestige", emoji="<:prestige:1350880286543712276>"),
            discord.SelectOption(label="Fast Custom", value="fast", emoji="<:premium:1350880299730473092>")
        ]
        super().__init__(placeholder="Choisissez un type de custom", options=options, custom_id="artwork_dropdown")

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        custom_data = load_json(ARTWORK_DATA)

        if user_id in custom_data:
            await interaction.response.send_message(
                "❌ Vous avez déjà un custom en cours !",
                ephemeral=True
            )
            return

        custom_type = "prestige" if self.values[0] == "prestige" else "fast"

        if custom_type == "fast":
            embed = discord.Embed(
                title="Confirmation de paiement",
                description="Êtes-vous sûr de vouloir payer **20 000 Bounds** pour une **Fast Custom** ?\n\nUne fois payé, vous recevrez un formulaire.",
                color=discord.Color.orange()
            )
            view = ConfirmTransactionView(interaction.user, self.bot, custom_type)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_modal(CustomForm(self.bot, interaction.user, custom_type))


class PersistentView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(ArtworkDropdown(bot))


class Artwork(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}L'événement : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")
        channel = self.bot.get_channel(ARTWORK_CHANNEL)

        if os.path.exists(ARTWORK_ID_MESSAGE):
            with open(ARTWORK_ID_MESSAGE, "r") as file:
                message_id = json.load(file).get("message_id")
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(view=PersistentView(self.bot))
                return
            except discord.NotFound:
                pass

        embed = discord.Embed(
            title="Racing Artwork by Natacha",
            description="Envie de transformer votre véhicule et le rendre unique ?\n\n"
                        "*\"Hellooo ! C'est moi Natacha la DA du serveur, je peux transformer vos idées en customs uniques et personnalisables à 100% UwU\"*\n\n"
                        "Vous avez la possibilité de commander :\n\n"
                        "💎 **Prestige Custom** – Disponible pour **10€**, limité à 2 fois par mois\n\n"
                        "Délai de réalisation : **7 à 10 heures**\n\n"
                        "🔥 **Fast Custom** – Obtenez une personnalisation ultra-rapide pour **20 000 Bounds**, limité à 3 fois par mois\n\n"
                        "Délai de réalisation : **2 à 3 heures**\n\n"
                        "⚠️ Toute demande en **MP** au <@&1347305124036350074> automobile est formellement interdite.\n\n"
                        "Lors de votre commande, veuillez préciser :\n"
                        "- Le modèle sur lequel vous souhaitez un custom\n"
                        "- La plateforme sur laquelle vous jouez\n"
                        "- Vos inspirations et idées en descriptif",
            color=discord.Color.light_embed()
        )
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/1333883528768917574/1347857423691415592/l__1_-removebg"
                "-preview.png")

        message = await channel.send(embed=embed, view=PersistentView(self.bot))
        with open(ARTWORK_ID_MESSAGE, "w") as file:
            json.dump({"message_id": message.id}, file)


async def setup(bot):
    bot.add_view(PersistentView(bot))
    await bot.add_cog(Artwork(bot))
