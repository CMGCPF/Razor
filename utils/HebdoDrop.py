import json
import logging
import discord
from datetime import datetime
import pytz
from commands.HebdoDrop import HebdoDropView
from config import *

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    handlers=[
                        logging.FileHandler("bot_log.txt"),
                        logging.StreamHandler()
                    ])

logger = logging.getLogger(__name__)


async def check_hebdo_drop(self):
    logger.debug('Initialisation de check_hebdo_drop')
    drop_path = "DATA/HebdoDrop/hebdo_drop.json"

    try:
        with open(drop_path, "r", encoding="utf-8") as f:
            drops = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Le fichier 'hebdo_drop.json' est introuvable ou corrompu.")
        return

    if not drops:
        return

    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)
    modified = False

    async def update_embed_if_needed(self, drop_id, drop_info, should_have_buttons):
        try:
            annonce_channel = self.bot.get_channel(1327980406049603584)
            if not annonce_channel:
                logger.error("Salon d'annonce introuvable.")
                return False

            try:
                annonce_message = await annonce_channel.fetch_message(int(drop_id))
            except discord.NotFound:
                logger.warning(f"Le message du drop {drop_id} est introuvable.")
                return False
            except Exception as e:
                logger.error(f"Erreur lors de la récupération du message du drop {drop_id} : {e}")
                return False

            embed = discord.Embed(
                title="Razor stock - PRO$PER / RACE",
                description=(
                    f"C'est Razor <:KING:1316870764070174722>\n\n"
                    f"Écoute bien, j'ai un truc qui va te faire rêver.\n\n"
                    f"Une livraison spéciale vient tout droit de Rockport, des caisses de folie récemment saisies.\n\n"
                    f"Mais devine quoi ? J'ai réussi à les récupérer... à ma façon.\n\n"
                    f"Ces beautés sont maintenant à moi, et peut-être à toi… si t'as les bounds pour les mériter.\n\n"
                    f"Mais fais pas traîner !\n\n"
                    f"Mon stock est dispo seulement pour **deux semaines**. Après ça, tout part.\n\n"
                    f"Alors, t'attends quoi ? Prends une décision... ou reste dans l'ombre, comme tous les autres.\n\n"
                    f"<:STARS:1316870912938737675> **{drop_info['nom']} - {drop_info['prix']} bounds** <:STARS:1316870912938737675>"
                ),
                color=discord.Color.light_embed()
            )
            embed.set_image(url=drop_info["image_url"])

            view = HebdoDropView(message_id=str(drop_id), custom_id="buy_drop_unique") if should_have_buttons else None
            await annonce_message.edit(embed=embed, view=view)
            logger.info(f"Drop {drop_id} mis à jour.")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du drop {drop_id} : {e}")
            return False

    for drop_id, drop_info in drops.items():
        drop_date = drop_info["date"]
        drop_hour = drop_info.get("heure", 14)
        drop_minute = drop_info.get("minute", 30)

        try:
            drop_datetime = paris_tz.localize(
                datetime.strptime(drop_date, "%d-%m-%Y").replace(hour=drop_hour, minute=drop_minute)
            )
        except ValueError:
            logger.error(f"Format de date invalide pour le drop {drop_id}: {drop_date}")
            continue

        if not drop_info.get("traite", False) and now >= drop_datetime:
            logger.info(f"Condition validée pour drop {drop_id}, tentative de mise à jour.")
            success = await update_embed_if_needed(self, drop_id, drop_info, should_have_buttons=True)

            if success:
                drops[drop_id]["traite"] = True
                modified = True
            else:
                logger.warning(f"La mise à jour du drop {drop_id} a échoué, pas de marquage comme traité.")

    if modified:
        try:
            with open(drop_path, "w", encoding="utf-8") as f:
                json.dump(drops, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur lors de l'écriture du fichier 'hebdo_drop.json' : {e}")
