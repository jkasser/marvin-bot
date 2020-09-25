import yaml
import random
from discord.ext import commands

file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["prod"]["token"]

bot = commands.Bot(command_prefix=cfg["prod"]["prefix"])


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    print(f'We have logged in as {bot.user}')  # notification of login.
if __name__ == '__main__':
    bot.run(token)  # recall my token was saved!