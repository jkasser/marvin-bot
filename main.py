import yaml
import random
import discord
from discord.ext import commands
from discord import Spotify
from riot.riot_api import Riot
from data.quotes import *


file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["disc"]["token"]

bot = commands.Bot(command_prefix=cfg["disc"]["prefix"])


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
    if 'hi marvin' in message_text:
        await channel.send(f'Why bother, {message.author.name}...')
    elif 'towel' in message_text:
        await channel.send(towel_quote)
    elif 'life' in message_text:
        await channel.send(the_answer_to_life)
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(
        f'Hi {member.name}, welcome to my Discord server!'
    )


@bot.command(name='marvin', help='Check in on Marvin the depressed robot!')
async def marvin_quote(ctx):
    response = random.choice(marvin_quotes)
    await ctx.send(response)


@bot.command(name='lullaby', help='Let Marvin read you a lullaby!')
async def marvin_lullaby(ctx):
    await ctx.send(marvin_lullaby)


@bot.command(name='flipcoin', help='Having trouble making a decision? Let Marvin flip a coin for you!')
async def marvin_coin_flip(ctx):
    coin_choices = ['Heads', 'Tails']
    await ctx.send(f'Results are in!\nThe coin landed on: {random.choice(coin_choices)}')


@bot.command(name='clash', help='Get current and upcoming clash tournament schedule.')
async def get_clash(ctx):
    schedule = Riot().get_clash_schedule()
    await ctx.send(str(schedule))


@bot.command(name='whatsmyvibe', help='What you vibing too right now lil gangsta?')
async def get_vibe(ctx, user: discord.Member=None):
    user = user or ctx.author
    if len(user.activities) > 1:
        for activity in user.activities:
            if isinstance(activity, Spotify):
                await ctx.send(f'{user} is listening to {activity.title} by {activity.artist} on {activity.album}')
                break
            elif user.activities.index(activity) == len(user.activities) - 1 and not isinstance(activity, Spotify):
                await ctx.send('You ain\'t listening to shit!')
    else:
        if len(user.activities) ==1 and isinstance(user.activities[0], Spotify):
            await ctx.send(f'{user} is listening to {user.activity.title} by {user.activity.artist} on {user.activity.album}')
        else:
            await ctx.send('You ain\'t listening to shit!')


@bot.command(name='roll', help='Type !roll <max number> to get a random number between 0 and the max!')
async def roll_dice(ctx, max):
    await ctx.send(f'You rolled {random.randint(0, int(max))}')


async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

if __name__ == '__main__':
    bot.run(token)  # recall my token was saved!