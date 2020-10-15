import yaml
import discord
from discord.ext import commands
from data.quotes import *

# discord config
file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["disc"]["token"]
intents = discord.Intents().all()
bot = commands.Bot(command_prefix=cfg["disc"]["prefix"], intents=intents)

# Get the list of cogs
extensions = [
    'cogs.marvin',
    'cogs.todo',
    'cogs.riot',
    'cogs.jeopardy',
    'cogs.news',
    'cogs.reminder',
    'cogs.reddit',
    'cogs.rapid_api'
]


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    print(f'We have logged in as {bot.user}')  # notification of login.


@bot.event
async def on_message(message):  # event that happens per any message.
    # each message has a bunch of attributes. Here are a few.
    # check out more by print(dir(message)) for example.
    print(f"{message.channel}: {message.author}: {message.author.name}: {message.content}")

    message_text = message.content.strip().lower()
    channel = message.channel
    if message.author != bot.user:
        if 'hi marvin' in message_text:
            await channel.send(f'Why bother, {message.author.name}...')
        elif 'towel' in message_text:
            await channel.send(towel_quote)
        elif 'life' in message_text:
            await channel.send(the_answer_to_life)
        elif 'thumb' in message_text:
            await channel.send(thumb_quote)
        elif 'shut up' in message_text or 'be quiet' in message_text or 'stfu' in message_text:
            await channel.send(file=discord.File('./assets/media/shut_up.gif'))
        elif 'wtf' in message_text or 'what the fuck' in message_text or 'what the hell' in message_text:
            await channel.send(file=discord.File('./assets/media/wtf.gif'))
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


if __name__ == '__main__':
    for extension in extensions:
        bot.load_extension(extension)
    bot.run(token)