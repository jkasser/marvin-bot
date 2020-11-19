import yaml
import discord
import random
from discord.ext import commands
from data.quotes import *

# discord config
file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["disc"]["token"]
intents = discord.Intents().all()
bot = commands.Bot(command_prefix=cfg["disc"]["prefix"], intents=intents)


class UserInfo:
    USERS = None

    def check_if_users_ready(self):
        if self.USERS is None:
            return False
        else:
            return True


# Get the list of cogs
extensions = [
    'cogs.subscriptions',
    'cogs.marvin',
    'cogs.todo',
    'cogs.riot',
    'cogs.jeopardy',
    'cogs.news',
    'cogs.reminder',
    'cogs.reddit',
    'cogs.weather',
    'cogs.address_book',
    'cogs.translator',
    'cogs.poll',
    'cogs.covid'
]


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    await bot.change_presence(status=discord.Status.online, activity=discord.CustomActivity(name='Vibing'))
    print(f'We have logged in as {bot.user}')  # notification of login.


@bot.event
async def on_message(message):  # event that happens per any message.
    # each message has a bunch of attributes. Here are a few.
    # check out more by print(dir(message)) for example.
    print(f"{message.channel}: {message.author}: {message.author.name}: {message.content}")

    message_text = message.content.strip().lower()
    channel = message.channel
    if message.author != bot.user:
        if 'towel' in message_text:
            await channel.send(towel_quote)
        elif 'meaning of life' in message_text or 'answer to life' in message_text:
            await channel.send(the_answer_to_life)
        elif ' thumb ' in message_text:
            await channel.send(thumb_quote)
        elif 'shut up' in message_text or 'be quiet' in message_text or 'stfu' in message_text:
            await channel.send(file=discord.File('./assets/media/shut_up.gif'))
        elif 'wtf' == message_text or 'what the fuck' == message_text or 'what the hell' == message_text:
            await channel.send(file=discord.File('./assets/media/wtf.gif'))
        elif '<@!759093184219054120>' in message.content:
            response = random.choice(marvin_quotes)
            await channel.send(response)
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(
        f'Hi {member.name}, welcome to my Discord server! Type !help to see my command list!'
    )


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(error)

