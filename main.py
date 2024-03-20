import yaml
import os
import sys
import discord
from utils.roles import Permissions
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

WELCOME_CHANNEL = cfg["disc"][env]["welcome_channel"]


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            intents=intents,
            command_prefix=cfg["disc"]["prefix"],
            self_bot=True, strip_after_prefix=True
        )


bot = Bot()


# cogs
@bot.command()
async def load(extension):
    await bot.load_extension(f'cogs.{extension}')


@bot.command()
async def unload(extension):
    await bot.unload_extension(f'cogs.{extension}')


async def load_extensions():
    for cog in extensions:
        await bot.load_extension(cog)
    # for filename in os.listdir('./cogs'):
    #     if filename.endswith('.py'):
    #         await bot.load_extension(f'cogs.{filename[:-3]}')


class UserInfo:
    USERS = None

    def check_if_users_ready(self):
        if self.USERS is None:
            return False
        else:
            return True


# Get the list of cogs
extensions = [
    # "cogs.subscriptions",
    "cogs.marvin",
    "cogs.riot",
    # "cogs.jeopardy",
    # "cogs.news",
    # "cogs.reddit",
    # "cogs.weather",
    # "cogs.address_book",
    # "cogs.phone",
    # "cogs.giphy",
    # "cogs.marvin_tube",
    # "cogs.plex"
]


@bot.event
async def on_ready():
    print('Logged in as: {0.user.name}\nBots user id: {0.user.id}'.format(bot))
    print('Discord.py version:')
    print(discord.__version__)
    print('Ready!')
    # load our cogs
    await load_extensions()
    # do our role logic here too
    channel = bot.get_channel(WELCOME_CHANNEL)
    await channel.purge()
    embed = discord.Embed(
        title="Select Your Roles!",
        description="React with the corresponding emoji to get the role! If you wish to have a role removed please "
                    "contact an Admin!",
        color=0xff0000,
    )
    for emoji, role in Permissions.permissions_list.items():
        embed.add_field(
            name=emoji,
            value=role[1],
            inline=True,
        )
    embed.set_footer(text="Welcome to our server!")
    msg = await channel.send(embed=embed)
    for emoji, role in Permissions.permissions_list.items():
        await msg.add_reaction(emoji)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.channel_id != WELCOME_CHANNEL or payload.member.bot:
        return
    if str(payload.emoji) in Permissions.permissions_list.keys():
        role_id = Permissions.permissions_list[str(payload.emoji)][0]
        await payload.member.add_roles(discord.utils.get(payload.member.guild.roles, id=role_id))


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    guild = await bot.fetch_guild(payload.guild_id)
    member = await guild.fetch_member(payload.user_id)
    if payload.channel_id != WELCOME_CHANNEL or member.bot:
        return
    if str(payload.emoji) in Permissions.permissions_list.keys():
        role_id = Permissions.permissions_list[str(payload.emoji)][0]
        await member.remove_roles(discord.utils.get(member.guild.roles, id=role_id))


@bot.event
async def on_message(message):
    print(
        f"{message.channel}: {message.author}: {message.content}"
    )
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(
        f"Hi {member.name}, welcome to my Discord server! Please take a brief second to select the channels you wish to access!"
    )


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(error)


if __name__ == '__main__':
    bot.run(token)

