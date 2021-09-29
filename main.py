import yaml
import os
import sys
import discord
import random
import asyncio
from discord.ext import commands
from assets.data.quotes import *
from concurrent.futures.thread import ThreadPoolExecutor
# from chatterbot import ChatBot
# from chatterbot.response_selection import get_random_response
# from chatterbot.trainers import ChatterBotCorpusTrainer

# discord config
with open('config.yaml', 'r') as file:
    cfg = yaml.safe_load(file)
env = os.environ.get('ENV', 'NOT SET')
if env == 'NOT SET':
    sys.exit('Set your environment first. E.g.:\n'
             'Windows: set ENV=dev\n'
             'Linux: export ENV=dev')
token = cfg["disc"][env]["token"]
intents = discord.Intents().all()
bot = commands.Bot(command_prefix=cfg["disc"]["prefix"], intents=intents)

# Instantiate our Chat Bot
# chatbot = ChatBot(
#     'Marvin',
#     storage_adapter='chatterbot.storage.SQLStorageAdapter',
#     database_uri='sqlite:///marvin.db',
#     logic_adapters=
#     [
#         {
#             "import_path": "chatterbot.logic.BestMatch",
#             "statement_comparison_function": "chatterbot.comparisons.levenshtein_distance",
#             "response_selection_method": get_random_response,
#             "default_response": "I am sorry, but I do not understand.",
#         },
#     ]
# )
# trainer = ChatterBotCorpusTrainer(chatbot)
# trainer.train("chatterbot.corpus.english")
# trainer.train("chatterbot.corpus.french")
# trainer.train("chatterbot.corpus.german")
# trainer.train("chatterbot.corpus.russian")
# trainer.train("./assets/data/custom.yml")



class UserInfo:
    USERS = None

    def check_if_users_ready(self):
        if self.USERS is None:
            return False
        else:
            return True


# Get the list of cogs
extensions = [
    # 'cogs.subscriptions',
    # 'cogs.marvin',
    # 'cogs.todo',
    # 'cogs.riot',
    # 'cogs.jeopardy',
    # 'cogs.news',
    # 'cogs.reminder',
    # 'cogs.reddit',
    # 'cogs.weather',
    # 'cogs.address_book',
    # 'cogs.translator',
    # 'cogs.poll',
    # # 'cogs.covid'
    # 'cogs.phone',
    # 'cogs.giphy',
    # 'cogs.jokes'
    'cogs.chat'
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
        elif message.channel.id == cfg["disc"][env]["chat_bot_channel"]:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(ThreadPoolExecutor(), bot.get_cog('MarvinChat').chatbot_response, message_text)
            await channel.send(response)
            # await channel.send(chatbot.get_response(message.content.capitalize()))
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


if __name__ == '__main__':
    for extension in extensions:
        bot.load_extension(extension)
    bot.run(token)
