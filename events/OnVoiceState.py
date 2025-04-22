import logging
import discord
import asyncio
import json
import random
from datetime import datetime, timedelta

import pytz
from discord.ext import commands
from colorama import Fore, Style, init as colorama_init

from utils.PlayerDataRequest import *
from config import *

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)
DOUBLE_BOUNDS_FILE = "DATA/JSON/double_bounds_log.json"
DOUBLE_BOUNDS_CHANNEL_ID = 1352694169704861870


def load_double_bounds_log():
    try:
        with open(DOUBLE_BOUNDS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_double_bounds_log(data):
    with open(DOUBLE_BOUNDS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_random_time():
    start_time = datetime.now().replace(hour=8, minute=45, second=0, microsecond=0)
    end_time = datetime.now().replace(hour=23, minute=59, second=0, microsecond=0)
    random_seconds = random.randint(0, int((end_time - start_time).total_seconds()))
    return start_time + timedelta(seconds=random_seconds)


def is_double_bounds_launched_today():
    double_bounds_log = load_double_bounds_log()
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    return today_date_str in double_bounds_log


def should_give_bounds(member: discord.Member) -> bool:
    if not member.voice or not member.voice.channel:
        logger.debug(f"{member.name} n'est pas en vocal.")
        return False

    members = [m for m in member.voice.channel.members if not m.bot]
    if len(members) <= 1:
        logger.debug(f"Pas assez de membres en vocal pour {member.name}.")
        return False

    if len(members) == 2:
        other = next(m for m in members if m.id != member.id)
        if other.voice.self_deaf or other.voice.self_mute:
            logger.debug(f"{other.name} est mute/deaf, pas de bounds pour {member.name}.")
            return False

    return True


def get_double_bounds_from_log():
    double_bounds_log = load_double_bounds_log()
    today_date_str = datetime.now().strftime("%Y-%m-%d")

    if today_date_str in double_bounds_log:
        heure_debut_str = double_bounds_log[today_date_str].get("heure_debut")
        heure_fin_str = double_bounds_log[today_date_str].get("heure_fin")
        if heure_debut_str and heure_fin_str:
            today = datetime.now().date()
            heure_debut = datetime.combine(today, datetime.strptime(heure_debut_str, "%H:%M").time())
            heure_fin = datetime.combine(today, datetime.strptime(heure_fin_str, "%H:%M").time())
            return heure_debut, heure_fin
    return None, None


async def delete_last_messages(channel: discord.TextChannel, limit: int):
    try:
        messages = [message async for message in channel.history(limit=limit)]
        if messages:
            await channel.delete_messages(messages)
            logger.info(f"{len(messages)} message(s) supprimé(s) dans {channel.name}.")
        else:
            logger.info("Aucun message à supprimer.")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des messages : {e}", exc_info=True)


class OnVoiceState(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.voice_timers = {}
        self.double_bounds_active = False
        self.double_bounds_start = None
        self.double_bounds_end = None
        self.embed_message_id = None
        self.double_bounds_packet_sent = False

        if not is_double_bounds_launched_today():
            self.schedule_random_double_bounds()
        else:
            logger.debug("Le multiplicateur a déjà été lancé aujourd'hui.")

        bot.loop.create_task(self.check_and_send_embed(at_startup=True))

    async def check_and_send_embed(self, at_startup=False):
        await self.bot.wait_until_ready()
        double_bounds_log = load_double_bounds_log()
        today_date_str = datetime.now().strftime("%Y-%m-%d")

        if self.double_bounds_end and datetime.now().time() > self.double_bounds_end.time():
            if self.double_bounds_packet_sent:
                logger.info("Fin de période double_bounds, reset du flag d'envoi.")
                self.double_bounds_packet_sent = False

        heure_debut, heure_fin = get_double_bounds_from_log()
        if not heure_debut or not heure_fin:
            logger.error("Les heures de début et de fin ne sont pas définies dans le log.")
            return

        if today_date_str not in double_bounds_log or not double_bounds_log[today_date_str].get("embed_id"):
            paris_tz = pytz.timezone('Europe/Paris')
            paris_time = datetime.now(paris_tz)
            current_hour = paris_time.time()

            if heure_debut.time() <= current_hour < heure_fin.time():
                logger.info(
                    "L'embed n'a pas encore été envoyé et nous sommes dans l'intervalle horaire, envoi en cours...")
                await self.announce_double_bounds()
            else:
                logger.info("L'embed n'a pas encore été envoyé, mais nous ne sommes pas dans l'intervalle horaire.")

        elif at_startup:
            logger.info("L'embed a déjà été envoyé aujourd'hui.")


        while True:
            await asyncio.sleep(60)
            double_bounds_log = load_double_bounds_log()
            today_date_str = datetime.now().strftime("%Y-%m-%d")

            if today_date_str in double_bounds_log and double_bounds_log[today_date_str].get("embed_id"):
                continue

            paris_tz = pytz.timezone('Europe/Paris')
            paris_time = datetime.now(paris_tz)
            current_hour = paris_time.time()

            if heure_debut.time() <= current_hour < heure_fin.time():
                double_bounds_log = load_double_bounds_log()
                if today_date_str not in double_bounds_log or not double_bounds_log[today_date_str].get("embed_id"):
                    logger.info("Envoi de l'embed car nous sommes dans l'intervalle horaire.")
                    await self.announce_double_bounds()
            else:
                logger.info("L'heure actuelle n'est pas dans l'intervalle de double bounds.")

            if self.double_bounds_start and self.double_bounds_end:
                if self.double_bounds_start.time() <= current_hour < self.double_bounds_end.time():
                    if not self.embed_message_id:
                        await self.announce_double_bounds()
                        logger.info("Multiplicateur lancé.")

    def cog_unload(self):
        for timer in self.voice_timers.values():
            timer.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f"{Fore.GREEN}L'événement : {Style.BRIGHT}{Fore.YELLOW}{__name__}{Style.RESET_ALL}{Fore.GREEN} est chargé !{Style.RESET_ALL}")

        await asyncio.sleep(5)

        for guild in self.bot.guilds:
            for member in guild.members:
                if member.voice and member.voice.channel:
                    if should_give_bounds(member) and str(member.id) not in self.voice_timers:
                        self.voice_timers[str(member.id)] = asyncio.create_task(
                            self.give_bounds(str(member.id), member))
                    else:
                        logger.info(f"{member.name} ne remplit pas les conditions.")

    def schedule_random_double_bounds(self):
        now = datetime.now()
        self.double_bounds_start = get_random_time()

        if self.double_bounds_start < now:
            self.double_bounds_start += timedelta(days=1)

        self.double_bounds_end = self.double_bounds_start + timedelta(hours=1)

        logger.info(
            f"Multiplicateur : {self.double_bounds_start.strftime('%H:%M')} à {self.double_bounds_end.strftime('%H:%M')}")
        logger.debug(f"double_bounds_start: {self.double_bounds_start}, double_bounds_end: {self.double_bounds_end}")

        if not self.double_bounds_start or not self.double_bounds_end:
            logger.error("Erreur: double_bounds_start ou double_bounds_end n'ont pas été initialisées correctement.")
            return

        today_date_str = self.double_bounds_start.strftime("%Y-%m-%d")
        double_bounds_log = load_double_bounds_log()

        double_bounds_log[today_date_str] = {
            "heure_debut": self.double_bounds_start.strftime("%H:%M"),
            "heure_fin": self.double_bounds_end.strftime("%H:%M"),
            "embed_id": None,
            "participants": {}
        }

        save_double_bounds_log(double_bounds_log)

    def is_double_bounds_active(self):
        now = datetime.now().time()
        return self.double_bounds_start.time() <= now <= self.double_bounds_end.time()

    async def announce_double_bounds(self):
        channel = self.bot.get_channel(DOUBLE_BOUNDS_CHANNEL_ID)

        if self.double_bounds_end is None or self.double_bounds_start is None:
            self.double_bounds_start, self.double_bounds_end = get_double_bounds_from_log()

        adjusted_end_time = self.double_bounds_end

        if channel:
            await delete_last_messages(channel, 3)
            message = await channel.send("<@&1309504308672204840> <@&1309503558315544576>")
            embed = discord.Embed(
                title="**BOUNDS X2 - PRO$PER /RACE **",
                description=f"C'est l'heure de faire chauffer l'asphalte ! **BOUNDS X2 ACTIVÉS** pour **1 HEURE SEULEMENT !**<:BAM:1316870393838960640>\n\n"
                            f"Cramponnez-vous, lâchez les chevaux et empochez le double avant que ça s’évapore <:STARS:1316870912938737675>\n\n"
                            f"Fini à **{adjusted_end_time.strftime('%H:%M')}**",
                color=discord.Color.light_embed()
            )
            embed.set_image(
                url='https://cdn.discordapp.com/attachments/1333883528768917574/1352624839319359539/OPPORTUNITIES_1'
                    '.gif?ex=67deb18c&is=67dd600c&hm=0342d99800765fad0e5bd4008062a4c16cb1b6854f345dba0a15e3a700e160a1&')
            message = await channel.send(embed=embed)
            self.embed_message_id = message.id
            double_bounds_log = load_double_bounds_log()
            today_date_str = datetime.now().strftime("%Y-%m-%d")
            double_bounds_log[today_date_str] = {
                "heure_debut": self.double_bounds_start.strftime("%H:%M"),
                "heure_fin": self.double_bounds_end.strftime("%H:%M"),
                "embed_id": self.embed_message_id,
                "participants": {}
            }
            save_double_bounds_log(double_bounds_log)
            try:
                import socket
                packet = {
                    "name": "double_bounds",
                    "activate": True
                }
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(("45.158.77.201", 10060))
                    s.sendall(json.dumps(packet).encode())
                self.double_bounds_packet_sent = True
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi du paquet double_bounds : {e}", exc_info=True)

            return message

    async def give_bounds(self, user_id: str, member: discord.Member):
        if self.double_bounds_start is None or self.double_bounds_end is None:
            self.double_bounds_start, self.double_bounds_end = get_double_bounds_from_log()
            if self.double_bounds_start is None or self.double_bounds_end is None:
                logger.error("Impossible de récupérer les heures de début et de fin pour les double bounds.")
                return

        while user_id in self.voice_timers:
            try:
                if member.voice and member.voice.channel:
                    members = [m for m in member.voice.channel.members if not m.bot]
                    if len(members) > 1:
                        player_data = load_player_data()
                        if user_id not in player_data:
                            player_data[user_id] = {"username": member.name, "bounds": 0}
                        bonus = BOUNDS_VOCAL
                        if any(role.id == BOOSTER_ROLE_ID for role in member.roles):
                            bonus += BOOSTER_BONUS_VOC
                        paris_tz = pytz.timezone('Europe/Paris')
                        paris_time = datetime.now(paris_tz)
                        current_hour = paris_time.time()

                        # print(f"Heure actuelle: {current_hour} | Heure début X2: {self.double_bounds_start} | Heure fin X2: {self.double_bounds_end}")
                        if self.double_bounds_start.time() <= current_hour < self.double_bounds_end.time():
                            bonus *= 2
                            logger.debug(f"Multiplicateur X2 appliqué : bonus = {bonus}")
                            double_bounds_log = load_double_bounds_log()
                            date_str = datetime.now().strftime("%Y-%m-%d")
                            if date_str not in double_bounds_log:
                                double_bounds_log[date_str] = {
                                    "heure_debut": self.double_bounds_start.strftime("%H:%M"),
                                    "heure_fin": self.double_bounds_end.strftime("%H:%M"),
                                    "embed_id": self.embed_message_id,
                                    "participants": {}
                                }

                            if user_id not in double_bounds_log[date_str]["participants"]:
                                double_bounds_log[date_str]["participants"][user_id] = {
                                    "username": member.name,
                                    "bounds_gagnes": 0
                                }

                            double_bounds_log[date_str]["participants"][user_id]["bounds_gagnes"] += bonus
                            save_double_bounds_log(double_bounds_log)
                            del double_bounds_log[date_str]["participants"][user_id]["bounds_gagnes"]

                            player_data[user_id]["bounds"] += bonus
                            save_player_data(player_data)
                            logger.info(
                                f"{member.name} a reçu {bonus} bounds. Total: {player_data[user_id]['bounds']}")
                        else:
                            player_data[user_id]["bounds"] += bonus
                            save_player_data(player_data)
                            logger.info(
                                f"{member.name} a reçu {bonus} bounds. Total: {player_data[user_id]['bounds']}")

                    for m in members:
                        m_id = str(m.id)
                        if m_id not in self.voice_timers and should_give_bounds(m):
                            self.voice_timers[m_id] = asyncio.create_task(self.give_bounds(m_id, m))

                    await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Erreur dans give_bounds : {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if member.bot:
            return

        user_id = str(member.id)

        if user_id in USER_ID:
            logger.info(f"{member.name} est dans la liste des exclus, pas d'XP attribué.")
            return

        if not should_give_bounds(member):
            if user_id in self.voice_timers:
                self.voice_timers[user_id].cancel()
                del self.voice_timers[user_id]
                logger.info(f"{member.name} ne remplit plus les conditions, timer arrêté.")
            return

        if after.channel and not before.channel:
            if user_id not in self.voice_timers:
                self.voice_timers[user_id] = asyncio.create_task(self.give_bounds(user_id, member))
        elif not after.channel and before.channel:
            if user_id in self.voice_timers:
                self.voice_timers[user_id].cancel()
                del self.voice_timers[user_id]
                logger.info(f"{member.name} a quitté le salon vocal.")

        elif after.channel and before.channel and after.channel != before.channel:
            if user_id not in self.voice_timers and should_give_bounds(member):
                self.voice_timers[user_id] = asyncio.create_task(self.give_bounds(user_id, member))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnVoiceState(bot))
