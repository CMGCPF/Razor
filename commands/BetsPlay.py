import asyncio
from datetime import datetime

import discord
import pytz
from discord.ext import commands
from discord import app_commands

import logging
import json
import os

from colorama import Fore, Style
from colorama import init as colorama_init

from config import *
from events.OnVoiceState import get_double_bounds_from_log
from utils.PlayerDataRequest import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)

CATEGORY_ID = 1327981647219654677


class ConfirmationAnnulationView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, requester: discord.Member, bets: dict):
        super().__init__()
        self.channel = channel
        self.requester = requester
        self.bets = bets

    @discord.ui.button(label="Oui", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requester:
            await interaction.response.send_message("**Vous n'avez pas initié cette annulation.**", ephemeral=True)
            return

        self.bets.pop(str(self.channel.id), None)
        save_bets(self.bets)

        await self.channel.delete()

    @discord.ui.button(label="Non", style=discord.ButtonStyle.success)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requester:
            await interaction.response.send_message("**Vous n'avez pas initié cette annulation.**", ephemeral=True)
            return

        await interaction.response.send_message("**L'annulation du pari a été annulée.**", ephemeral=True)
        self.stop()


class BetView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, amount: int, embed_id: int,
                 channel_id: int):
        super().__init__(timeout=None)
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.embed_id = embed_id
        self.channel_id = channel_id

        bets = load_bets()
        if str(self.channel_id) in bets and bets[str(self.channel_id)].get("accepted", False):
            for child in self.children:
                child.disabled = True

    @discord.ui.button(label="Oui", style=discord.ButtonStyle.success, custom_id="OuiButton")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("**Tu n'es pas le joueur défié !**", ephemeral=True)
            return

        bets = load_bets()
        if str(self.channel_id) in bets:
            bets[str(self.channel_id)]["accepted"] = True
            save_bets(bets)

        await interaction.message.edit(
            content=f"{self.challenger.mention}, {self.opponent.mention} a accepté le pari !", view=None)
        await interaction.channel.send(
            embed=discord.Embed(
                title="Défi accepté !",
                description="Le **prochain screenshot envoyé dans ce salon** servira de preuve.\n\nUn administrateur doit prendre la décision.\n\nVous pouvez tout de même parler entre vous, mais si une image est envoyée, elle sera comptée comme une preuve.",
                color=discord.Color.light_embed()
            )
        )

    @discord.ui.button(label="Non", style=discord.ButtonStyle.danger, custom_id="NonButton")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("**Tu n'es pas le joueur défié !**", ephemeral=True)
            return

        await interaction.channel.delete()
        bets = load_bets()
        bets.pop(str(self.channel_id), None)
        save_bets(bets)


class ResultView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member, bet_amount: int, channel_id: int):
        super().__init__(timeout=None)
        self.player_data = load_player_data()
        self.player1 = player1
        self.player2 = player2
        self.bet_amount = bet_amount
        self.channel_id = channel_id
        self.lock = asyncio.Lock()
        self.children[0].label = f"{self.player1.name}"
        self.children[1].label = f"{self.player2.name}"

    async def disable_buttons(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    async def record_result(self, interaction: discord.Interaction, winner: str):
        bets = load_bets()
        if str(self.channel_id) in bets:
            bets[str(self.channel_id)]["winner"] = winner
            save_bets(bets)
        await self.disable_buttons(interaction)

    async def handle_winner_selection(self, interaction: discord.Interaction, winner: discord.Member,
                                      loser: discord.Member, winner_key: str):
        bets = load_bets()
        if str(self.channel_id) in bets and "winner" in bets[str(self.channel_id)]:
            await interaction.response.send_message("**Un gagnant a déjà été défini pour ce pari !**", ephemeral=True)
            return

        await self.process_winner(interaction, winner, loser)
        await self.record_result(interaction, winner_key)
        await interaction.response.send_message(f"**{winner.mention} a gagné avec succès !**", ephemeral=True)

    @discord.ui.button(label="Joueur 1", style=discord.ButtonStyle.primary, custom_id="Joueur1Button")
    async def win_player1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("**Seuls les administrateurs peuvent valider le gagnant.**",
                                                    ephemeral=True)
            return
        await self.handle_winner_selection(interaction, self.player1, self.player2, "player1")

    @discord.ui.button(label="Joueur 2", style=discord.ButtonStyle.primary, custom_id="Joueur2Button")
    async def win_player2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("**Seuls les administrateurs peuvent valider le gagnant.**",
                                                    ephemeral=True)
            return
        await self.handle_winner_selection(interaction, self.player2, self.player1, "player2")

    @discord.ui.button(label="Aucun gagnant", style=discord.ButtonStyle.danger, custom_id="NoWinnerButton")
    async def no_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("**Seuls les administrateurs peuvent valider le gagnant.**",
                                                    ephemeral=True)
            return

        async with self.lock:
            bets = load_bets()
            if str(self.channel_id) in bets and "winner" in bets[str(self.channel_id)]:
                await interaction.response.send_message("**Un gagnant a déjà été défini pour ce pari !**",
                                                        ephemeral=True)
                return

            await interaction.response.send_message("**Aucun des deux participants n'a gagné !**", ephemeral=True)
            await self.record_result(interaction, "none")

            embed = discord.Embed(
                title="Résultat du pari",
                description="Aucun gagnant, les bounds ne sont pas transférés.",
                color=discord.Color.orange()
            )
            view = CloseChannelView(channel_id=interaction.channel.id)
            await interaction.channel.send(embed=embed, view=view)
            await self.disable_buttons(interaction)

    async def process_winner(self, interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
        try:
            self.player_data = load_player_data()

            winner_id = str(winner.id)
            loser_id = str(loser.id)

            if winner_id not in self.player_data:
                self.player_data[winner_id] = {"bounds": 0}
            if loser_id not in self.player_data:
                self.player_data[loser_id] = {"bounds": 0}

            if self.player_data[loser_id]["bounds"] < self.bet_amount:
                await interaction.response.send_message(
                    f"❌ **Erreur:** {loser.mention} n'a pas assez de bounds pour finaliser le pari.",
                    ephemeral=True
                )
                return

            self.player_data[winner_id]["bounds"] += self.bet_amount
            self.player_data[loser_id]["bounds"] -= self.bet_amount

            save_player_data(self.player_data)

            transactions = load_transactions()
            timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
            transactions.setdefault(loser_id, []).append({
                "action": f"**-{self.bet_amount}** <:bounds_c:1346948316193357917> | Perte du pari contre {winner.mention}",
                "date": f"<t:{timestamp}:R>"
            })
            transactions.setdefault(winner_id, []).append({
                "action": f"**+{self.bet_amount}** <:bounds_b:1346948303887274005> | Gagnant du pari contre {loser.mention}",
                "date": f"<t:{timestamp}:R>"
            })
            save_transactions(transactions)

            embed = discord.Embed(
                title="Résultat du pari",
                description=f"🏆 **{winner.mention}** a gagné contre **{loser.mention}** !\n💰 **Gain:** {self.bet_amount} bounds",
                color=discord.Color.green()
            )
            view = CloseChannelView(channel_id=interaction.channel.id)
            print(f"{winner.mention} a gagné contre {loser.mention} | Gain {self.bet_amount} bounds")

            await interaction.channel.send(embed=embed, view=view)
            await self.disable_buttons(interaction)

            self.player_data = None

        except KeyError as e:
            logger.error(f"Erreur : Clé manquante dans les données du joueur : {e}")
            await interaction.response.send_message(
                "❌ **Une erreur s'est produite lors du traitement du gagnant.** Veuillez réessayer ou contacter un "
                "administrateur.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erreur inattendue dans process_winner : {e}")
            await interaction.response.send_message(
                "❌ **Une erreur inattendue s'est produite.** Veuillez réessayer ou contacter un administrateur.",
                ephemeral=True
            )


class CloseChannelView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Fermer le salon", style=discord.ButtonStyle.danger, custom_id="CloseChannelButton")
    async def close_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("**Seuls les administrateurs peuvent fermer ce salon.**",
                                                    ephemeral=True)
            return

        bets = load_bets()
        bets.pop(str(self.channel_id), None)
        save_bets(bets)

        await interaction.channel.delete()


class Bet(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bets = {}
        self.player_data = load_player_data()

    def is_already_in_bet(self, user_id: int) -> bool:
        return any(user_id in (bet['challenger'], bet['opponent']) for bet in self.bets.values())

    async def reload_bets(self):
        bets = load_bets()
        self.bets = {int(k): v for k, v in bets.items()}

        for channel_id, bet in bets.items():
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue

            challenger = channel.guild.get_member(bet["challenger"])
            opponent = channel.guild.get_member(bet["opponent"])
            if not challenger or not opponent:
                continue

            embed_message = await channel.fetch_message(bet["embed_id"])
            if embed_message:
                view = None if bet.get("accepted", False) else BetView(challenger, opponent, bet["amount"],
                                                                       bet["embed_id"], int(channel_id))
                await embed_message.edit(view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")
        await self.reload_bets()

    @commands.hybrid_command(name="annuler", with_app_command=True,
                             description="Annule un pari en cours")
    async def annuler_pari(self, ctx: commands.Context):
        bets = load_bets()
        channel_id = str(ctx.channel.id)

        if channel_id not in bets:
            await ctx.send("**Aucun pari en cours dans ce salon.**", ephemeral=True)
            return

        bet_info = bets[channel_id]
        if bet_info.get("accepted", False):
            await ctx.send("**Le pari a déjà été accepté, il ne peut plus être annulé !**", ephemeral=True)
            return

        is_admin = ctx.author.guild_permissions.administrator
        is_owner = ctx.author.id == bet_info["challenger"]

        if not (is_owner or is_admin):
            await ctx.send("**Seul le créateur du pari ou un administrateur peut annuler ce pari.**", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="Confirmation d'annulation",
            description="Êtes-vous sûr de vouloir annuler ce pari ?",
            color=discord.Color.orange()
        )

        if is_admin:
            confirm_embed.set_footer(text="Vous pouvez annuler ce pari grâce à vos permissions administratives.")

        view = ConfirmationAnnulationView(ctx.channel, ctx.author, bets)
        await ctx.send(embed=confirm_embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="pari", with_app_command=True,
                             description="Pariez avec un membre sur une playlist.")
    @app_commands.choices(
        mode_de_jeu=[
            app_commands.Choice(name="Playlist de course", value="playlist_course"),
            app_commands.Choice(name="Playlist de drag", value="playlist_drag"),
            app_commands.Choice(name="Playlist JCJ", value="playlist_jcj"),
            app_commands.Choice(name="Playlist pro du drift", value="playlist_pro_du_drift"),
            app_commands.Choice(name="Playlist de traque", value="playlist_traque"),
            app_commands.Choice(name="Playlist flics vs pilote", value="playlist_flics_vs_pilote"),
            app_commands.Choice(name="Autre", value="autre")
        ]
    )
    async def parie(self, ctx: commands.Context, member: discord.Member, montant: int,
                    mode_de_jeu: app_commands.Choice[str]):
        await self.reload_bets()

        if member.bot or member == ctx.author:
            return await ctx.send("**Tu ne peux pas parier contre toi-même ou un bot !**", ephemeral=True)

        if self.is_already_in_bet(ctx.author.id) or self.is_already_in_bet(member.id):
            return await ctx.send("**L'un des joueurs est déjà dans un pari en cours !**", ephemeral=True)

        if montant < 1:
            await ctx.send(f"**Le montant du pari doit être supérieur à 0.**", ephemeral=True)
            return

        if self.player_data is None:
            self.player_data = {}

        user_id = str(ctx.author.id)
        opponent_id = str(member.id)

        player_data = load_player_data()

        if user_id not in player_data or player_data[user_id]["bounds"] < montant:
            return await ctx.send("Tu n'as pas assez de bounds pour ce pari.", ephemeral=True)

        if opponent_id not in player_data or player_data[opponent_id]["bounds"] < montant:
            return await ctx.send(f"{member.mention} n'a pas assez de bounds pour ce pari.", ephemeral=True)

        del player_data[user_id]
        del player_data[opponent_id]

        self.player_data = None

        guild = ctx.guild
        category = discord.utils.get(guild.categories, id=CATEGORY_ID)
        if not category:
            return await ctx.send("La catégorie de pari n'existe pas !", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.author: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                use_application_commands=True
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                use_application_commands=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                use_application_commands=True
            )
        }

        ephemeral_message = await ctx.send(f"Création du pari...", ephemeral=True)
        channel_name = f"pari-{ctx.author.name}-vs-{member.name}"
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)

        self.bets[channel.id] = {"challenger": ctx.author.id, "opponent": member.id, "amount": montant}
        embed = discord.Embed(title="Défi lancé !",
                              description=f"{ctx.author.mention} défie {member.mention} pour `{montant}` bounds"
                                          f".\nAcceptez-vous ce pari ?"
                                          f"\n\n**Mode choisi :** \n{mode_de_jeu.name}",
                              color=discord.Color.light_embed())
        message = await channel.send(content=member.mention, embed=embed)
        view = BetView(ctx.author, member, montant, message.id, channel.id)
        await message.edit(view=view)

        bets = load_bets()
        bets[str(channel.id)] = {
            "challenger": ctx.author.id,
            "opponent": member.id,
            "amount": montant,
            "embed_id": message.id,
            "date": datetime.utcnow().isoformat()
        }
        save_bets(bets)
        if ephemeral_message:
            try:
                await ctx.interaction.delete_original_response()
            except discord.errors.NotFound:
                pass

        await ctx.send(f"Le pari a été créé dans {channel.mention} !", ephemeral=True)

    def is_double_bounds_now():
        heure_debut, heure_fin = get_double_bounds_from_log()
        if not heure_debut or not heure_fin:
            return False
        current_time = datetime.now().time()
        return heure_debut.time() <= current_time < heure_fin.time()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        try:
            self.player_data = load_player_data()
            bets = load_bets()

            user_id = str(message.author.id)
            if user_id not in self.player_data:
                self.player_data[user_id] = {"bounds": 50}
            else:
                bonus = 50

                if any(role.id == BOOSTER_ROLE_ID for role in message.author.roles):
                    bonus += BOOSTER_BONUS_MESS

                if self.is_double_bounds_now():
                    bonus *= 2
                    logger.info(f"Multiplicateur X2 appliqué à {message.author.name}")

                self.player_data[user_id]["bounds"] += bonus
                logger.info(
                    f"{message.author.name} a reçu {bonus} bounds. Total: {self.player_data[user_id]['bounds']}")

            save_player_data(self.player_data)

            if str(message.channel.id) not in bets:
                self.player_data = None
                return

            bet_info = bets[str(message.channel.id)]
            if "proof" in bet_info:
                self.player_data = None
                return

            if message.attachments:
                bet_info["proof"] = message.attachments[0].url
                save_bets(bets)

                embed = discord.Embed(
                    title="Preuve du pari",
                    description=f"Preuve du pari entre {message.guild.get_member(bet_info['challenger']).mention} et {message.guild.get_member(bet_info['opponent']).mention}.",
                    color=discord.Color.light_embed()
                )
                embed.set_image(url=message.attachments[0].url)
                await message.channel.send(embed=embed, view=ResultView(
                    message.guild.get_member(bet_info['challenger']),
                    message.guild.get_member(bet_info['opponent']),
                    bet_info["amount"],
                    message.channel.id
                ))
                await message.delete()

            self.player_data = None

        except Exception as e:
            logger.error(f"Erreur dans on_message : {e}")
            self.player_data = None
            await message.channel.send("❌ **Une erreur s'est produite.** Veuillez réessayer plus tard.")


async def setup(bot: commands.Bot) -> None:
    bet_cog = Bet(bot)
    await bot.add_cog(bet_cog)
    await bet_cog.reload_bets()
