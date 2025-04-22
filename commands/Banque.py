import logging
import json
import os
from datetime import datetime
import pytz

from colorama import Fore, Style
from colorama import init as colorama_init

import discord
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


class TransactionView(discord.ui.View):
    def __init__(self, bot, member, transactions, balance, page=1):
        super().__init__(timeout=None)
        self.bot = bot
        self.member = member
        self.transactions = transactions
        self.balance = balance
        self.page = page
        self.per_page = 5  # Afficher 5 transactions par page
        self.total_pages = max(1, (len(self.transactions) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 1:
            self.add_item(PrevPageButton(self))
        if self.page < self.total_pages:
            self.add_item(NextPageButton(self))

    async def update_message(self, interaction):
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        page_transactions = self.transactions[start:end]

        history_text = "\n".join([f"{t['date']} - {t['action']}" for t in page_transactions])

        description = f"**Solde actuel :** {self.balance} <:bounds_b:1346948303887274005>\n\n" \
                      f"**Historique des transactions :**\n\n{history_text}"

        embed = discord.Embed(title=f"Compte de {self.member.name}", description=description,
                              color=discord.Color.light_embed())
        embed.set_footer(text=f"Page {self.page}/{self.total_pages} - {len(self.transactions)} transactions")
        embed.set_thumbnail(url=self.member.display_avatar.url)

        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


class PrevPageButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label="←", style=discord.ButtonStyle.primary, custom_id=f"prev_page_{view.member.id}")
        self._view = view

    async def callback(self, interaction: discord.Interaction):
        if self.view.page > 1:
            self.view.page -= 1
            await self.view.update_message(interaction)


class NextPageButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label="→", style=discord.ButtonStyle.primary, custom_id=f"next_page_{view.member.id}")
        self._view = view

    async def callback(self, interaction: discord.Interaction):
        if self.view.page < self.view.total_pages:
            self.view.page += 1
            await self.view.update_message(interaction)


class Bank(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not hasattr(self.bot, "persistent_views_added"):
            self.bot.persistent_views_added = False

        if not self.bot.persistent_views_added:
            transactions = load_transactions()
            for user_id, trans in transactions.items():
                member = self.bot.get_user(int(user_id))
                if member:
                    view = TransactionView(self.bot, member, trans, 0, page=1)
                    self.bot.add_view(view)
            self.bot.persistent_views_added = True

        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

    @commands.hybrid_command(name="virement", description="Envoyer des bounds à un autre membre")
    async def transfer_bounds(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("**Le montant doit être supérieur à 0.**")
            return

        player_data = load_player_data()
        sender_id, receiver_id = str(ctx.author.id), str(member.id)

        if sender_id not in player_data or player_data[sender_id]["bounds"] < amount:
            await ctx.send("**Fonds insuffisants.**")
            return

        if sender_id == receiver_id:
            await ctx.send("**Vous ne pouvez pas vous envoyer de l'argent à vous-même.**")
            return

        player_data[sender_id]["bounds"] -= amount
        if receiver_id not in player_data:
            player_data[receiver_id] = {"username": member.name, "bounds": 0}
        player_data[receiver_id]["bounds"] += amount
        save_player_data(player_data)

        transactions = load_transactions()
        timestamp = int(datetime.now(pytz.timezone("Europe/Paris")).timestamp())
        transactions.setdefault(sender_id, []).append({
            "action": f"**-{amount}** <:bounds_c:1346948316193357917> | Virement vers {member.mention}",
            "date": f"<t:{timestamp}:R>"
        })
        transactions.setdefault(receiver_id, []).append({
            "action": f"**+{amount}** <:bounds_b:1346948303887274005> | Virement de {ctx.author.mention}",
            "date": f"<t:{timestamp}:R>"
        })
        save_transactions(transactions)

        await ctx.send(f"**{ctx.author.mention} a envoyé {amount} bounds à {member.mention} !**", ephemeral=True)

    @commands.hybrid_command(name="compte", description="Voir les bounds d'un utilisateur et ses transactions")
    async def view_account(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_id = str(member.id)
        player_data = load_player_data()
        transactions = load_transactions()

        if user_id not in player_data:
            await ctx.send("**Cet utilisateur n'a pas encore de compte.**", ephemeral=True)
            return

        balance = player_data[user_id]["bounds"]
        transaction_history = transactions.get(user_id, [])

        if not transaction_history:
            description = f"**Solde actuel :** {balance} <:bounds_b:1346948303887274005>\n\n" \
                          f"**Historique des transactions :**\n\n Aucune transaction enregistrée."

            embed = discord.Embed(title=f"Compte de {member.name}", description=description,
                                  color=discord.Color.light_embed())
            embed.set_thumbnail(url=member.display_avatar.url)
            await ctx.send(embed=embed)
            return

        transaction_history.sort(key=lambda x: x['date'], reverse=True)

        view = TransactionView(self.bot, member, transaction_history, balance, page=1)

        start = (view.page - 1) * view.per_page
        end = start + view.per_page

        embed = discord.Embed(
            title=f"Compte de {member.name}",
            description=f"**Solde actuel :** {balance} <:bounds_b:1346948303887274005>\n\n"
                        f"**Historique des transactions :**\n\n"
                        f"{''.join([f'{t['date']} {t['action']} \n' for t in transaction_history[start:end]])}",
            color=discord.Color.light_embed()
        )
        embed.set_footer(text=f"Page {view.page}/{view.total_pages} - {len(transaction_history)} transactions")
        embed.set_thumbnail(url=member.display_avatar.url)

        await ctx.send(embed=embed, view=view)

        @self.view_account.error
        async def view_account_error(self, ctx, error):
            if isinstance(error, discord.errors.DiscordServerError):
                await ctx.send("Le serveur Discord rencontre un problème. Veuillez réessayer plus tard.",
                               ephemeral=True)
            else:
                logger.error(f"Erreur lors de l'exécution de la commande : {error}")
                await ctx.send("Une erreur est survenue. Veuillez réessayer plus tard.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bank(bot))
