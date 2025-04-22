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

PREPA_ORDER_DATA = "DATA/JSON/prepa_order_data.json"
PREPA_CHANNEL = 1309576274787696692
PREPA_DATA = "DATA/JSON/prepa_data.json"
PREPA_ID_MESSAGE = "DATA/JSON/prepa_id_message.json"
gala_id = 344036900551524353
prepa_role = 1319666143861932082
CATEGORY_PREPA = 1309500591776731179


def load_json(file_path):
    return json.load(open(file_path, "r")) if os.path.exists(file_path) else {}


def save_json(data, file_path):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def get_next_order_number():
    data = load_json(PREPA_ORDER_DATA)
    data["order_number"] = data.get("order_number", 0) + 1
    save_json(data, PREPA_ORDER_DATA)
    return data["order_number"]


class CustomView(discord.ui.View):
    def __init__(self, user, channel, message):
        super().__init__(timeout=None)
        self.user = user
        self.channel = channel
        self.message = message

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != gala_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        data = load_json(PREPA_DATA)
        user_data = data.get(str(self.user.id), {})
        user_data["status"] = "accepted"
        save_json(data, PREPA_DATA)

        await interaction.message.edit(view=None)
        await interaction.response.send_message("Commande acceptée !", ephemeral=True)

        view = None

        embed = self.message.embeds[0]
        await self.message.edit(embed=embed, view=view)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.red)
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != gala_id:
            await interaction.response.send_message("Vous n'avez pas la permission de faire cela.", ephemeral=True)
            return

        user_id = str(self.user.id)
        data = load_json(PREPA_DATA)
        data.pop(user_id, None)
        save_json(data, PREPA_DATA)

        player_data = load_json(PLAYER_DATA)

        if user_id in player_data:
            player_data[user_id]["bounds"] += 20000

        if str(gala_id) in player_data:
            player_data[str(gala_id)]["bounds"] -= 20000

        save_json(player_data, PLAYER_DATA)

        transactions = load_transactions()
        timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())

        transactions.setdefault(user_id, []).append({
            "action": f"**+20000** <:bounds_b:1346948303887274005> | Remboursement suite à un refus de <@{gala_id}>",
            "date": f"<t:{timestamp}:R>"
        })
        transactions.setdefault(str(gala_id), []).append({
            "action": f"**-20000** <:bounds_c:1346948316193357917> | Refus d’une préparation automobile de <@{user_id}>",
            "date": f"<t:{timestamp}:R>"
        })

        save_transactions(transactions)
        await self.channel.delete()


async def create_private_channel(guild, user, vehicule, inspiration, classe):
    data = load_json(PREPA_DATA)

    if str(user.id) in data:
        existing_channel_id = data[str(user.id)]["channel_id"]
        existing_channel = guild.get_channel(existing_channel_id)
        if existing_channel:
            return existing_channel

    category = discord.utils.get(guild.categories, id=CATEGORY_PREPA)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_member(gala_id): discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = await guild.create_text_channel(f"prepa-{user.name}", overwrites=overwrites, category=category)
    order_number = get_next_order_number()

    embed = discord.Embed(
        title=f"Commande #{order_number}",
        description=f"**Utilisateur** : {user.mention}\n\n"
                    f"**Information commande :**\n\n"
                    f"**Véhicule** : {vehicule}\n"
                    f"**Classe** : {inspiration}\n"
                    f"**Type** : {classe}\n",
        color=discord.Color.light_embed()
    )

    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1333883528768917574/1352713315603714100/l__2_-removebg-preview.png?ex=67df03f2&is=67ddb272&hm=ef4ba121b3b8d4d1ef124aab28f36f6347ee217e55f402cb6e360ca1f5968e4d&"
    )

    view = CustomView(user, channel, None)
    message = await channel.send(embed=embed, view=view)
    view.message = message

    data[str(user.id)] = {
        "channel_id": channel.id,
        "message_id": message.id,
        "order_number": order_number,
        "form_data": {
            "vehicule": vehicule,
            "classes": classe,
            "inspiration": inspiration
        }
    }
    save_json(data, PREPA_DATA)

    return channel, message.id


class CustomForm(discord.ui.Modal):
    def __init__(self, bot, user):
        super().__init__(title="Préparation automobile", timeout=None)
        self.bot = bot
        self.user = user

        self.vehicule = discord.ui.TextInput(label="Véhicule",
                                             placeholder="Exemple : Ford Mustang GT 2015",
                                             required=True)
        self.classe = discord.ui.TextInput(label="Classe",
                                           placeholder="Exemple : B, A, A+, S, S+",
                                           required=True)
        self.inspiration = discord.ui.TextInput(label="Type",
                                                placeholder="Exemple : drift, sprint, circuit",
                                                required=True)
        self.add_item(self.vehicule)
        self.add_item(self.classe)
        self.add_item(self.inspiration)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vehicule = self.vehicule.value.strip()
            classe = self.classe.value.strip()
            inspiration = self.inspiration.value.strip()

            if not vehicule or not inspiration:
                await interaction.response.send_message("Veuillez remplir tous les champs du formulaire.",
                                                        ephemeral=True)
                return

            player_data = load_json(PLAYER_DATA)
            user_id = str(self.user.id)
            cost = 20000

            if user_id not in player_data or player_data[user_id]["bounds"] < cost:
                await interaction.response.send_message("❌ Fonds insuffisants !", ephemeral=True)
                return

            player_data[user_id]["bounds"] -= cost
            gala_data = player_data.get(str(gala_id), {"bounds": 0})
            gala_data["bounds"] += cost
            player_data[str(gala_id)] = gala_data
            save_json(player_data, PLAYER_DATA)

            transactions = load_transactions()
            timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
            transactions.setdefault(user_id, []).append({
                "action": f"**-20000** <:bounds_c:1346948316193357917> | Achat d'une préparation automobile de <@{gala_id}>",
                "date": f"<t:{timestamp}:R>"
            })
            transactions.setdefault(gala_id, []).append({
                "action": f"**+20000** <:bounds_b:1346948303887274005> | Achat d'une préparation automobile de <@{user_id}>",
                "date": f"<t:{timestamp}:R>"
            })
            save_transactions(transactions)

            transaction_data = load_json(PREPA_ORDER_DATA)
            user_id = str(interaction.user.id)

            now = datetime.now(timezone)
            formatted_time = now.strftime("%d/%m/%Y %H:%M:%S")

            transaction_data[user_id] = {
                "form_data": {
                    "vehicule": vehicule,
                    "classes": classe,
                    "inspiration": inspiration,
                },
                "date_commande": formatted_time
            }
            save_json(transaction_data, PREPA_ORDER_DATA)

            await create_private_channel(interaction.guild, self.user,
                                         vehicule, classe, inspiration)

            await interaction.response.send_message("Commande confirmée et enregistrée !", ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur lors de la soumission du formulaire : {e}")
            await interaction.response.send_message(
                "❌ Une erreur s'est produite lors du traitement de votre commande. Veuillez réessayer plus tard.",
                ephemeral=True)


class ConfirmTransactionView(discord.ui.View):
    def __init__(self, user, bot):
        super().__init__(timeout=None)
        self.user = user
        self.bot = bot

    @discord.ui.button(label="✅ Oui", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(CustomForm(self.bot, self.user))

    @discord.ui.button(label="❌ Non", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Commande annulée.", ephemeral=True)


class PrestigePrepaButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Je veux une prépa", style=discord.ButtonStyle.primary, emoji="💎",
                         custom_id="prestige_order")
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        custom_data = load_json(PREPA_DATA)

        if user_id in custom_data:
            await interaction.response.send_message("❌ Vous avez déjà un custom en cours !", ephemeral=True)
            return

        embed = discord.Embed(
            title="Confirmation de paiement",
            description="Êtes-vous sûr de vouloir payer **20 000 Bounds** pour une **Préparation Automobile** ?\n\n"
                        "Une fois payé, vous recevrez un formulaire.",
            color=discord.Color.light_embed()
        )
        view = ConfirmTransactionView(interaction.user, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PersistentView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(PrestigePrepaButton(bot))


class PrestigePrepa(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}L'événement : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")
        channel = self.bot.get_channel(PREPA_CHANNEL)

        if os.path.exists(PREPA_ID_MESSAGE):
            with open(PREPA_ID_MESSAGE, "r") as file:
                message_id = json.load(file).get("message_id")
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(view=PersistentView(self.bot))
                return
            except discord.NotFound:
                pass

        embed = discord.Embed(
            title="**Prestige Prepa by Gala **",
            description="Voilà ce qu’il me faut pour que ta caisse soit prête à dominer :\n\n"
                        " - Le nom complet de la voiture (exemple : Ford Mustang GT 2015 – ouais, sois précis).\n\n"
                        " - La classe où tu veux qu’elle joue (tu peux en choisir une ou deux, mais choisis bien – ça pourrait te coûter la victoire).\n\n"
                        " - Le type de course où elle va briller (drift, sprint, circuit, peu importe, fais ton choix).\n\n"
                        "<:ONTARGET:1316870474474717205> Règles du jeu :\n\n"
                        " - Pas plus de deux commandes par personne par semaine.\n\n"
                        " - Les délais ? Entre 1 et 3 jours. Ouais, l’excellence prend du temps.\n\n",
            color=discord.Color.light_embed()
        )
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/1333883528768917574/1352713315603714100/l__2_-removebg-preview.png?ex=67df03f2&is=67ddb272&hm=ef4ba121b3b8d4d1ef124aab28f36f6347ee217e55f402cb6e360ca1f5968e4d&")

        message = await channel.send(embed=embed, view=PersistentView(self.bot))
        with open(PREPA_ID_MESSAGE, "w") as file:
            json.dump({"message_id": message.id}, file)


async def setup(bot):
    bot.add_view(PersistentView(bot))
    await bot.add_cog(PrestigePrepa(bot))
