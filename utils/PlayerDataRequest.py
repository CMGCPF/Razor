import json
import os
from config import *


def load_data(file_path, default_value={}):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    return default_value


def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_transactions():
    return load_data(TRANSACTION_FILE)


def save_transactions(data):
    save_data(TRANSACTION_FILE, data)


def load_player_data():
    return load_data(PLAYER_DATA)


def save_player_data(data):
    save_data(PLAYER_DATA, data)


def load_leaderboard_message_id():
    data = load_data(LEADERBOARD_MESSAGE_FILE, {})
    return data.get("message_id", None)


def save_leaderboard_message_id(message_id):
    save_data(LEADERBOARD_MESSAGE_FILE, {"message_id": message_id})


def load_bets():
    return load_data(BET_FILE)


def save_bets(bets):
    save_data(BET_FILE, bets)
