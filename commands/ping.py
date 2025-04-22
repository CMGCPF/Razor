import discord
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, MissingPermissions
from discord import Embed, Color
import json, time
from datetime import datetime, timedelta
import os
from colorama import init as colorama_init
from colorama import Fore, Style
import logging

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}La commande : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargée !{Style.RESET_ALL}")

    @commands.hybrid_command(name='ping', with_app_command=True,
                             description='Vous donne les latences du bot.',
                             aliases=['latance', 'p', 'pi', 'pin', 'bug', 'b', 'bu'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ping(self, ctx):
        start_time = time.perf_counter()
        message = await ctx.send("Calcul des latences...", ephemeral=True)
        message_ping = (time.perf_counter() - start_time) * 1000

        bot_latency = round(self.bot.latency * 1000, 2)
        api_latency = round(message_ping - bot_latency, 2)

        embed = discord.Embed(title="🏓 Pong!",
                              description="Latences du bot ",
                              color=discord.Color.dark_embed())
        embed.add_field(name="Latance du Bot  🖥️", value=f"{bot_latency} ms", inline=False)
        embed.add_field(name="Latance du Message  📩", value=f"{message_ping:.2f} ms", inline=False)
        embed.add_field(name="Latance de l'API  🌐", value=f"{api_latency} ms", inline=False)

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await message.edit(content=None, embed=embed)

        logger.info(f"{Fore.YELLOW}La commande ping a été utilisée par : {Fore.CYAN}{ctx.author}{Style.RESET_ALL}")

    @ping.error
    async def help_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            time_left = round(error.retry_after)
            await ctx.send(f"Vous devez attendre encore **{time_left}** seconde(s).", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))
