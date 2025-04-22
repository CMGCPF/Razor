import os
import json
import discord
from colorama import Fore, Style
from discord.ext import commands
from discord import app_commands
from config import INVENTORY_DIR, PLAYER_DATA, MARKET_DIR, MARKET_CHANNEL_ID, MARKET_EMBED_FILE
from utils.PlayerDataRequest import *


def load_player_data(user_id):
    with open(PLAYER_DATA, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get(str(user_id), {"bounds": 0})


def save_player_data(user_id, player_data):
    with open(PLAYER_DATA, "r", encoding="utf-8") as file:
        data = json.load(file)

    data[str(user_id)] = player_data

    with open(PLAYER_DATA, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


class VoitureSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Voir les voitures disponibles", options=options)

    async def callback(self, interaction: discord.Interaction):
        data = json.loads(self.values[0])
        vendeur_id = data["vendeur_id"]
        voiture_nom = data["nom"]
        prix = data["prix"]

        file_path = os.path.join(MARKET_DIR, vendeur_id, f"{voiture_nom}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                voiture_data = json.load(f)

            voiture = {
                "nom": voiture_data["nom"],
                "prix": voiture_data["prix_public"],
                "image_url": voiture_data.get("image_url", "")
            }

            embed = discord.Embed(
                title=f"{voiture['nom']} - {prix} bounds",
                color=discord.Color.light_embed()
            )
            embed.add_field(name="Vendeur", value=f"<@{vendeur_id}>", inline=False)
            embed.add_field(name="Prix", value=f"{voiture['prix']} bounds", inline=False)
            if voiture["image_url"]:
                embed.set_image(url=voiture["image_url"])

            view = BuyButtonView(voiture, vendeur_id, self.view.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Fichier de la voiture introuvable.", ephemeral=True)


class MarketView(discord.ui.View):
    def __init__(self, options, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(VoitureSelect(options))


class BuyButtonView(discord.ui.View):
    def __init__(self, voiture, vendeur_id, bot):
        super().__init__(timeout=60)
        self.voiture = voiture
        self.vendeur_id = vendeur_id
        self.bot = bot

    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.primary)
    async def acheter(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = ConfirmBuyView(self.voiture, self.vendeur_id, self.bot)

        embed = discord.Embed(title="Confirmation d'achat", color=discord.Color.light_embed())
        embed.add_field(name="Voiture", value=self.voiture['nom'], inline=False)
        embed.add_field(name="Prix", value=f"{self.voiture['prix']} bounds", inline=False)
        embed.add_field(name="Vendeur", value=f"<@{self.vendeur_id}>", inline=False)
        if self.voiture.get("image_url"):
            embed.set_image(url=self.voiture["image_url"])

        await interaction.response.edit_message(embed=embed, view=confirm_view)


class ConfirmBuyView(discord.ui.View):
    def __init__(self, voiture, vendeur_id, bot):
        super().__init__(timeout=60)
        self.voiture = voiture
        self.vendeur_id = vendeur_id
        self.bot = bot

    @discord.ui.button(label="Oui", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        buyer_id = str(interaction.user.id)
        prix = int(self.voiture["prix"])

        if buyer_id == self.vendeur_id:
            return await interaction.response.send_message("Vous ne pouvez pas acheter votre propre voiture !",
                                                           ephemeral=True)

        with open(PLAYER_DATA, "r", encoding="utf-8") as file:
            data = json.load(file)

        if data.get(buyer_id, {}).get("bounds", 0) < prix:
            return await interaction.response.send_message("Vous n'avez pas assez de bounds !", ephemeral=True)

        data[buyer_id]["bounds"] -= prix
        data[self.vendeur_id]["bounds"] += prix

        with open(PLAYER_DATA, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

        market_user_path = os.path.join(MARKET_DIR, self.vendeur_id)
        voiture_file_name = None

        for file in os.listdir(market_user_path):
            if file.endswith(".json"):
                with open(os.path.join(market_user_path, file), "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if content.get("nom") == self.voiture["nom"]:
                        voiture_file_name = file
                        break

        if not voiture_file_name:
            return await interaction.response.send_message("Voiture introuvable dans le marché.", ephemeral=True)

        voiture_path = os.path.join(market_user_path, voiture_file_name)

        with open(voiture_path, "r", encoding="utf-8") as f:
            voiture_data = json.load(f)

        voiture_data.pop("vendeur_id", None)
        voiture_data.pop("prix_public", None)

        buyer_inventory_path = os.path.join(INVENTORY_DIR, buyer_id)
        os.makedirs(buyer_inventory_path, exist_ok=True)

        existing_files = [f for f in os.listdir(buyer_inventory_path) if
                          f.startswith("voiture-") and f.endswith(".json")]
        new_index = len(existing_files) + 1
        new_voiture_filename = f"voiture-{new_index}.json"
        new_voiture_path = os.path.join(buyer_inventory_path, new_voiture_filename)

        with open(new_voiture_path, "w", encoding="utf-8") as f:
            json.dump(voiture_data, f, indent=4)

        os.remove(voiture_path)

        vendeur = await self.bot.fetch_user(int(self.vendeur_id))
        if vendeur:
            await vendeur.send(
                f"Votre voiture **{self.voiture['nom']}** a été achetée par {interaction.user.mention} pour {prix} bounds !")

        embed = discord.Embed(title="Achat confirmé !", color=discord.Color.light_embed())
        embed.add_field(name="Voiture", value=self.voiture['nom'], inline=False)
        embed.add_field(name="Prix", value=f"{prix} bounds", inline=False)
        embed.add_field(name="Vendeur", value=f"<@{self.vendeur_id}>", inline=False)
        embed.set_thumbnail(url=self.voiture['image_url'])

        await self.bot.get_cog("Vente").update_market_embed()
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Non", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Achat annulé.", view=None)


class VenteVoitureSelect(discord.ui.Select):
    def __init__(self, voiture_data, user_id, vente_type, bot):
        options = []
        voiture_nom_count = {}

        for nom, voiture in voiture_data.items():
            if nom in voiture_nom_count:
                voiture_nom_count[nom] += 1
            else:
                voiture_nom_count[nom] = 1

            label = f"{nom} #{voiture_nom_count[nom]}"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=f"{user_id}_{nom}_{voiture_nom_count[nom]}",
                    emoji="<:shop:1345795606165323817>"
                )
            )

        super().__init__(placeholder="Choisissez une voiture à vendre", options=options)
        self.voiture_data = voiture_data
        self.user_id = str(user_id)
        self.vente_type = vente_type
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        data = self.values[0].split("_")
        voiture_nom = data[1]
        voiture_num = int(data[2])

        voiture = self.voiture_data.get(voiture_nom)

        user_inventory_path = os.path.join(INVENTORY_DIR, self.user_id)
        market_user_path = os.path.join(MARKET_DIR, self.user_id)
        os.makedirs(market_user_path, exist_ok=True)
        voiture_file_name = f"{voiture['nom']}.json"
        new_voiture_path = os.path.join(market_user_path, voiture_file_name)

        new_price = int(float(voiture["prix"]) * 1.2)
        voiture["prix_public"] = new_price
        voiture["vendeur_id"] = self.user_id

        for file in os.listdir(user_inventory_path):
            file_path = os.path.join(user_inventory_path, file)
            if file.endswith(".json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)

                    if content.get("nom") == voiture["nom"]:
                        os.remove(file_path)
                        break

                except Exception as e:
                    print(f"Erreur lors de la suppression de {file_path} : {e}")

        with open(new_voiture_path, "w", encoding="utf-8") as f:
            json.dump(voiture, f, indent=4)

        voiture_path = os.path.join(user_inventory_path, f"voiture-{self.values[0]}.json")
        if os.path.exists(voiture_path):
            os.remove(voiture_path)

        await self.bot.get_cog("Vente").update_market_embed()
        await interaction.response.send_message(f"Votre voiture {voiture['nom']} #{voiture_num} a été mise en vente !",
                                                ephemeral=True)


class MarketBuySelect(discord.ui.Select):
    def __init__(self, market_files, bot):
        options = []
        for vendeur_id, voiture in market_files:
            options.append(
                discord.SelectOption(
                    label=f"{voiture['nom']} - {voiture['prix_public']} bounds",
                    value=json.dumps({
                        "vendeur_id": vendeur_id,
                        "nom": voiture['nom'],
                        "prix": voiture['prix_public'],
                        "image_url": voiture.get("image_url", "")
                    })
                )
            )
        super().__init__(placeholder="Choisissez une voiture à acheter", options=options)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        data = json.loads(self.values[0])
        vendeur_id = data["vendeur_id"]
        voiture = {
            "nom": data["nom"],
            "prix": data["prix"],
            "image_url": data.get("image_url", "")
        }

        embed = discord.Embed(title="Détails de la voiture", color=discord.Color.light_embed())
        embed.add_field(name="Voiture", value=voiture["nom"], inline=False)
        embed.add_field(name="Prix", value=f"{voiture['prix']} bounds", inline=False)
        embed.add_field(name="Vendeur", value=f"<@{vendeur_id}>", inline=False)
        if voiture["image_url"]:
            embed.set_image(url=voiture["image_url"])

        await interaction.response.send_message(embed=embed, view=BuyButtonView(voiture, vendeur_id, self.bot),
                                                ephemeral=True)


class Vente(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def save_embed_message_id(self, message_id):
        with open(MARKET_EMBED_FILE, "w", encoding="utf-8") as file:
            json.dump({"message_id": message_id}, file, indent=4)

    def load_embed_message_id(self):
        if os.path.exists(MARKET_EMBED_FILE):
            with open(MARKET_EMBED_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data.get("message_id")
        return None

    async def update_market_embed(self):
        channel = self.bot.get_channel(MARKET_CHANNEL_ID)
        if not channel:
            print("Marché non trouvé !")
            return

        market_embed = discord.Embed(
            title="The shopnetwork by Razor ",
            description="YO, ÉCOUTE BIEN ÇA !\n\n"
                        "Bienvenue dans le Shop Network , la nouvelle place pour les vrais pilotes.\n\n"
                        "Ici, t’as une chance en or de faire tourner ton business et d’écouler tes caisses… mais avec un twist.\n\n"
                        "Le deal est simple : Tu veux vendre ton bolide ? T’as deux options. Soit tu la vend directement au prix coûtant, soit tu la balances en public… mais là, ça change tout.\n\n"
                        "Ouais, tu m’as bien entendu. Si tu mets ta caisse en vente pour tout le monde, les autres devront allonger 20% de plus pour se l’offrir.\n\n"
                        "Pourquoi ? Parce que c’est la loi du marché, mon pote. \n\n"
                        "La rareté, ça se paie en bounds.\n\n"
                        "Alors, t’attends quoi ?\n\n"
                        "Poste ta caisse  et regarde les bounds pleuvoir.\n\n"
                        "T’as le talent, t’as les bagnoles… \n\n"
                        "Maintenant, montre-nous que t’as le business.",

            color=discord.Color.light_embed()
        )
        market_embed.set_thumbnail(
            url='https://cdn.discordapp.com/attachments/1333883528768917574/1358006742927015946/image.png?ex=67f245d6&is=67f0f456&hm=ae5029dc08eaec0ef69441062b57c1b008f699921203db19e0cd52eef5f20f91&')
        view = discord.ui.View()

        options = []
        market_files = []

        for user_folder in os.listdir(MARKET_DIR):
            user_path = os.path.join(MARKET_DIR, user_folder)
            if os.path.isdir(user_path):
                for file in os.listdir(user_path):
                    if file.endswith(".json"):
                        file_path = os.path.join(user_path, file)
                        with open(file_path, "r", encoding="utf-8") as f:
                            voiture_data = json.load(f)
                            market_files.append((user_folder, voiture_data))
                            options.append(
                                discord.SelectOption(
                                    label=f"{voiture_data['nom']} - {voiture_data['prix_public']} bounds",
                                    value=json.dumps({
                                        "vendeur_id": user_folder,
                                        "nom": voiture_data['nom'],
                                        "prix": voiture_data['prix_public']
                                    })
                                )
                            )

        if options:
            view = MarketView(options, self.bot)

        else:
            market_embed.add_field(name="Aucune voiture disponible", value="Revenez plus tard !", inline=False)
            view = discord.ui.View()

        message_id = self.load_embed_message_id()

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=market_embed, view=view)
            except discord.NotFound:
                new_message = await channel.send(embed=market_embed, view=view)
                self.save_embed_message_id(new_message.id)
        else:
            new_message = await channel.send(embed=market_embed, view=view)
            self.save_embed_message_id(new_message.id)

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")

        await self.update_market_embed()

    @app_commands.command(name="vendre", description="Vendez une voiture de votre inventaire.")
    @commands.has_permissions(administrator=True)
    @app_commands.choices(
        vente_type=[
            app_commands.Choice(name="Vente directe", value="directe"),
            app_commands.Choice(name="Vente publique", value="publique"),
        ]
    )
    async def vendre(self, interaction: discord.Interaction, vente_type: app_commands.Choice[str]):
        user_id = str(interaction.user.id)
        user_inventory_path = os.path.join(INVENTORY_DIR, user_id)

        if not os.path.exists(user_inventory_path):
            return await interaction.response.send_message("Vous ne possédez aucun véhicule.", ephemeral=True)

        voiture_files = [f for f in os.listdir(user_inventory_path) if f.startswith("voiture-") and f.endswith(".json")]
        if not voiture_files:
            return await interaction.response.send_message("Vous n'avez aucune voiture à vendre.", ephemeral=True)

        voiture_data = {}
        for file_name in sorted(voiture_files):
            file_path = os.path.join(user_inventory_path, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    voiture_data[data["nom"]] = data
            except Exception as e:
                print(f"Erreur lors de la lecture de {file_name} : {e}")

        view = discord.ui.View()
        view.add_item(VenteVoitureSelect(voiture_data, user_id, vente_type.value, self.bot))

        embed = discord.Embed(title="Vente de voiture",
                              description="Sélectionnez la voiture que vous souhaitez vendre.",
                              color=discord.Color.light_embed())
        embed.add_field(name="Type de vente", value=vente_type.name, inline=False)

        await self.update_market_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @vendre.error
    async def vendre_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("**Vous n'avez pas la permission d'exécuter cette commande.**", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"**Vous devez attendre encore **{time_left}** seconde(s).**", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Vente(bot))
