import yaml
import os
import sys
import discord
from discord.ext import commands

# discord config
with open("config.yaml", "r") as file:
    cfg = yaml.safe_load(file)
env = os.environ.get("ENV", "NOT SET")
if env == "NOT SET":
    sys.exit(
        "Set your environment first. E.g.:\n"
        "Windows: set ENV=dev\n"
        "Linux: export ENV=dev"
    )
token = cfg["disc"][env]["token"]
intents = discord.Intents.all()

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            intents=intents,
            command_prefix=cfg["disc"]["prefix"],
            self_bot=True, strip_after_prefix = True
        )

client = Bot()


# cogs
@client.command()
async def load(extension):
    await client.load_extension(f'cogs.{extension}')


@client.command()
async def unload(extension):
    await client.unload_extension(f'cogs.{extension}')


async def load_extension():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await client.load_extension(f'cogs.{filename[:-3]}')


class UserInfo:
    USERS = None

    def check_if_users_ready(self):
        if self.USERS is None:
            return False
        else:
            return True


# Get the list of cogs
extensions = [
    "cogs.subscriptions",
    "cogs.marvin",
    "cogs.riot",
    "cogs.jeopardy",
    "cogs.news",
    "cogs.reddit",
    "cogs.weather",
    "cogs.address_book",
    "cogs.phone",
    "cogs.giphy",
    "cogs.marvin_tube",
    "cogs.plex"
]


@commands.Cog.listener()
async def on_ready(self):
    print('Logged in as: {0.user.name}\nBots user id: {0.user.id}'.format(self.client))
    print('Discord.py version:')
    print(discord.__version__)
    print('Ready!')


@commands.command()
async def ping(self, ctx):
    await ctx.send(f'Ping is {round(self.client.latency * 1000)} ms')


@commands.Cog.listener()
async def on_message(message):  # event that happens per any message.
    # each message has a bunch of attributes. Here are a few.
    # check out more by print(dir(message)) for example.
    print(
        f"{message.channel}: {message.author}: {message.author.name}: {message.content}"
    )

    message_text = message.content.strip().lower()
    channel = message.channel
    if message.author != client.user:
        if (
            "shut up" in message_text
            or "be quiet" in message_text
            or "stfu" in message_text
        ):
            await channel.send(file=discord.File("./assets/media/shut_up.gif"))
        elif (
            "wtf" == message_text
            or "what the fuck" == message_text
            or "what the hell" == message_text
        ):
            await channel.send(file=discord.File("./assets/media/wtf.gif"))
    await client.process_commands(message)


@client.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(
        f"Hi {member.name}, welcome to my Discord server! Type !help to see my command list!"
    )


@client.event
async def on_command_error(ctx, error):
    await ctx.send(error)
