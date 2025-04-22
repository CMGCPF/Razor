import os
import discord
import aiohttp
from discord.ext import commands
from colorama import init as colorama_init, Fore, Style
from dotenv import load_dotenv

load_dotenv()
colorama_init()

TOKEN = os.getenv("TOKEN")


async def count_lines():
    total_lines = 0
    for directory in ("./events", "./commands"):
        for filename in filter(lambda f: f.endswith(".py") and not f.startswith("_"), os.listdir(directory)):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                total_lines += sum(1 for _ in file)
    return total_lines


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), case_insensitive=True)
        self.button_starter = []
        self.role_members = {}
        self.session = None
        self.started = False

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        await self.load_cogs("events", "l'events")
        await self.load_cogs("commands", "La commande")
        await self.tree.sync()
        await self.display_startup_message()

    async def close(self):
        await super().close()
        if self.session:
            await self.session.close()

    async def on_ready(self):
        if not self.started:
            for button_class in self.button_starter:
                self.add_view(button_class())
            self.started = True
            await self.change_presence(status=discord.Status.online, activity=None)

    async def load_cogs(self, directory, cog_type):
        for filename in filter(lambda f: f.endswith(".py") and not f.startswith("_"), os.listdir(f"./{directory}")):
            cog_name = f"{directory}.{filename[:-3]}"
            try:
                await self.load_extension(cog_name)
                print(
                    f"{Fore.GREEN}{cog_type} : {Style.BRIGHT}{Fore.YELLOW}{cog_name}{Style.RESET_ALL}{Fore.GREEN} a été activé avec succès !{Style.RESET_ALL}")
            except Exception as e:
                print(
                    f"{Fore.RED}Erreur lors du chargement de {cog_type} {Style.BRIGHT}{Fore.YELLOW}{cog_name}{Style.RESET_ALL}{Fore.RED}: {e}{Style.RESET_ALL}")

    async def on_message(self, message):
        await self.process_commands(message)

    async def display_startup_message(self):
        line_length = 69
        total_lines = await count_lines()
        print("\n")
        print(f"     {Fore.GREEN}┏{'━' * (line_length - 2)}┓{Style.RESET_ALL}")
        print(f"     {Fore.GREEN}┃{' ' * (line_length - 2)}┃{Style.RESET_ALL}")
        print(f"     {Fore.GREEN}┃ {Fore.GREEN}{self.user}{Style.RESET_ALL}{' ' * (line_length - 3 - len(f'{self.user}'))}{Fore.GREEN}┃{Style.RESET_ALL}")
        print(f"     {Fore.GREEN}┃ {Fore.GREEN}Total des lignes de code : {total_lines}{Style.RESET_ALL}{' ' * (line_length - 3 - len(f'Total des lignes de code : {total_lines}'))}{Fore.GREEN}┃{Style.RESET_ALL}")
        print(f"     {Fore.GREEN}┃{' ' * (line_length - 2)}┃{Style.RESET_ALL}")
        print(f"     {Fore.GREEN}┗{'━' * (line_length - 2)}┛{Style.RESET_ALL}")
        print("\n")


bot = Bot()
bot.remove_command('help')
bot.run(TOKEN)
