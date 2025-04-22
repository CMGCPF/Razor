import logging
import discord
import asyncio
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from colorama import Fore, Style, init as colorama_init
from config import *
from utils.PlayerDataRequest import save_leaderboard_message_id, load_leaderboard_message_id

colorama_init()

logging.basicConfig(level=logging.INFO,
                    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.YELLOW}%(name)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


async def update_leaderboard(self):
    logger.debug('Initialisation de update_leaderboard')
    channel = self.bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    sorted_players = sorted(self.player_data.items(), key=lambda x: x[1].get("bounds", 0), reverse=True)[:10]
    leaderboard_text = "\n".join([
        f"`# {i + 1}` - <@{player[0]}> - `{player[1]['bounds']}` bounds" for i, player in enumerate(sorted_players)
    ])

    timer_edit = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(minutes=1)
    timestamp_text = f"\n\nMise à jour : <t:{int(timer_edit.timestamp())}:R>"

    embed = discord.Embed(title="Classement Forbes",
                          description=("Ahahah ! Voilà le classement des plus riches, gamin !\n\n"
                                       "Jette un œil et imprègne-toi bien de ce que ça représente...\n"
                                       "Parce que moi, Razor, je suis tout en haut.\n\n"
                                       + leaderboard_text + timestamp_text),
                          color=discord.Color.light_embed())
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1321081617070166017/1340046991484522536"
                            "/telecharge-removebg-preview.png?ex=67c2bbc3&is=67c16a43&hm"
                            "=a7ba2db61b6254c082612f3789217b2d37f07f8576df5cd57ce72fdbebe9477b&")

    message_id = load_leaderboard_message_id()

    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed)
            return
        except discord.NotFound:
            logger.warning("Message avec l'ID spécifié introuvable, envoi d'un nouveau leaderboard.")
        except discord.Forbidden:
            logger.error("Permissions insuffisantes pour modifier le message du leaderboard.")
            return
        except discord.HTTPException as e:
            logger.error(f"Erreur HTTP en modifiant le message du leaderboard: {e}")
            return

    try:
        new_message = await channel.send(embed=embed)
        save_leaderboard_message_id(new_message.id)
    except discord.Forbidden:
        logger.error("Permissions insuffisantes pour envoyer un message dans ce canal.")
    except discord.HTTPException as e:
        logger.error(f"Erreur HTTP en envoyant le message du leaderboard: {e}")
