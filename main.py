import yaml
import random
import discord
from discord.ext import commands, tasks
from discord import Spotify
from utils.riot_api import Riot
from utils.reminder import ReminderBot
import datetime
from data.quotes import *


file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["disc"]["token"]

bot = commands.Bot(command_prefix=cfg["disc"]["prefix"])
reminder = ReminderBot()


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    print(f'We have logged in as {bot.user}')  # notification of login.
    check_reminders.start()


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
            await ctx.send(f'{user.display_name} is listening to {user.activity.title} by {user.activity.artist} on {user.activity.album}')
        else:
            await ctx.send('You ain\'t listening to shit!')


@bot.command(name='roll', help='Type !roll <max number> to get a random number between 0 and the max!')
async def roll_dice(ctx, max):
    await ctx.send(f'You rolled {random.randint(0, int(max))}')


@bot.command(name='decide', help='Let marvin make a decision for you!')
async def decide(ctx):
    await ctx.send(f'{random.choice(["Yes.", "No."])}')


@bot.command(name='hangover', help='Get some medical advice from someone completely unqualified!')
async def hangover(ctx):
    await ctx.send(random.choice(hangover_cures))


@bot.command(name='addrole', pass_context=True)
@commands.has_any_role("Admins", "TheOGs")
async def add_role_to_user(ctx, user: discord.Member, role: discord.Role):
    await user.add_roles(role)
    await ctx.send(f'{ctx.author.name} has bestowed the role of {role.name} on {user.display_name}')


@bot.command(name='removerole', pass_context=True)
@commands.has_any_role("Admins", "TheOGs")
async def remove_role_from_user(ctx, user: discord.Member, role: discord.Role):
    await user.remove_roles(role)
    await ctx.send(f'{ctx.author.name} has removed the role of {role.name} from {user.display_name}')


@bot.command(name='getroles')
async def get_all_roles_in_channel(ctx):
    await ctx.send(", ".join([str(r.name) for r in ctx.guild.roles]))


@bot.command(name='remind', help='Let me remind you of something! Just type \"!remind <who> in <when> to <what>\" NOTE: There is a minimum polling interval of 10 seconds.')
async def create_reminder(ctx, *text, user: discord.Member=None):
    text = f'!remind {" ".join(text)}'
    now = datetime.datetime.utcnow()
    user = user or ctx.author
    channel_id = ctx.message.channel.id
    try:
        # parse the string into 3 fields to insert into the databse
        name, when, what = reminder.parse_reminder_text(text)
        if name.lower() == 'me':
            name = '@' + user.display_name
        # get the date as a datetime object
        when_datetime = reminder.get_when_remind_date(when, start_time=now)
        # now insert it into the db
        reminder.insert_reminder((name, when_datetime, what, channel_id))
        await ctx.send(f'I will remind {name} to {what} at {when_datetime}')
    except ValueError:
        await ctx.send('ERROR: Reminder was in an invalid format! Please use: !remind <who> in|on <when> to <what>')


@bot.command(name='makeprivate', help="Make a private channel for you and x members")
async def make_private_channel(ctx, * members:discord.Member):
    guild = ctx.guild
    creator = ctx.author
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True),
    }
    for member in members:
        overwrites[member]: discord.PermissionOverwrite(read_messages=True)
    channel_name = f'{creator.name}s-private-channel'
    potential_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if potential_channel is None:
        channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
        await ctx.send(f'Channel: {channel} has been created for you and {", ".join([member.name for member in members])}')
    elif potential_channel:
        await ctx.send(f'Channel: {channel_name} already exists! Modify it yourself and stop bothering me.')

@tasks.loop(seconds=10)
async def check_reminders():
    results = reminder.check_reminders()
    if len(results):
        # results are a tuple of index, name, when, what, channel_id, and sent
        for result in results:
            # check the when date to see if its => now
            if datetime.datetime.utcnow() >= result[2]:
                channel = bot.get_channel(result[4])
                await channel.send(f'{result[1]}! This is your reminder to: {result[3]}!')
                # set it as sent
                reminder.update_reminder(result[0])


async def on_error(ctx, event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            error_msg = f'Unhandled message: {args[0]}\n'
            f.write(error_msg)
            await ctx.send(error_msg)
        else:
            raise

if __name__ == '__main__':
    try:
        bot.run(token)  # recall my token was saved!
    except Exception:
        reminder.close_conn()