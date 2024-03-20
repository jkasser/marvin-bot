import discord
import random
import requests
import os
import asyncio
import yaml
from discord.ext import commands
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.named_queues = dict(General=[])
        with open("config.yaml", "r") as file:
            cfg = yaml.safe_load(file)
        env = os.environ.get("ENV", "NOT SET")
        self.booster_channel = cfg["disc"][env]["booster_lounge_channel"]

    @commands.command(name="latency", aliases=["ping"], help="Get my latency in ms.")
    async def get_latency(self, ctx):
        await ctx.send(f"My latency is {round(self.bot.latency * 1000, 1)}ms.")

    @commands.command(
        name="flipcoin",
        help="Having trouble making a decision? Let Marvin flip a coin for you!",
    )
    async def marvin_coin_flip(self, ctx):
        coin_choices = ["Heads", "Tails"]
        await ctx.send(
            f"Results are in!\nThe coin landed on: {random.choice(coin_choices)}"
        )

    @commands.command(
        name="whatsmyvibe", help="What you vibing to right now?"
    )
    async def get_vibe(self, ctx, user: discord.Member = None):
        web_url = "https://open.spotify.com/track/"
        user = user or ctx.author  # default to the caller
        spot = next(
            (
                activity
                for activity in user.activities
                if isinstance(activity, discord.Spotify)
            ),
            None,
        )
        if spot is None:
            await ctx.send(f"{user.name.capitalize()} is not listening to Spotify.")
            return
        embedspotify = discord.Embed(
            title=f"{user.name.capitalize()}'s Spotify", color=0x1EBA10
        )

        embedspotify.add_field(name="Artist", value=spot.artist, inline=False)
        embedspotify.add_field(name="Album", value=spot.album)
        embedspotify.set_thumbnail(url=spot.album_cover_url)
        url = web_url + spot.track_id
        await ctx.send(embed=embedspotify)
        await ctx.send(url)

    @commands.command(
        name="roll",
        help="Type !roll <max number> to get a random number between 0 and the max!",
    )
    async def roll_dice(self, ctx, max_roll):
        await ctx.send(f"You rolled {random.randint(0, int(max_roll))}")

    @commands.command(name="decide", help="Let marvin make a decision for you!")
    async def decide(self, ctx):
        await ctx.send(f'{random.choice(["Yes.", "No."])}')

    @commands.command(name="addrole", pass_context=True)
    @commands.has_any_role("Admins")
    async def add_role_to_user(self, ctx, user: discord.Member, role: discord.Role):
        await user.add_roles(role)
        await ctx.send(
            f"{ctx.author.name} has bestowed the role of {role.name} on {user.display_name}"
        )

    @commands.command(name="removerole", pass_context=True)
    @commands.has_any_role("Admins")
    async def remove_role_from_user(
        self, ctx, user: discord.Member, role: discord.Role
    ):
        await user.remove_roles(role)
        await ctx.send(
            f"{ctx.author.name} has removed the role of {role.name} from {user.display_name}"
        )

    @commands.command(name="getroles")
    async def get_all_roles_in_channel(self, ctx):
        await ctx.send(", ".join([str(r.name) for r in ctx.guild.roles]))

    @commands.command(
        name="adduser",
        help="Add a user to the channel. You must be an Admin to use this command.",
    )
    @commands.has_any_role("Admins")
    async def add_user_to_channel(self, ctx, *users):
        members = await ctx.guild.fetch_members(limit=150).flatten()
        for user in users:
            for member in members:
                if user in member.name:
                    try:
                        perms = ctx.message.channel.overwrites_for(member)
                        perms.send_messages = True
                        perms.read_messages = True
                        perms.attach_files = True
                        perms.embed_links = True
                        perms.read_message_history = True
                        perms.mention_everyone = True
                        perms.use_external_emojis = True
                        perms.attach_files = True
                        perms.speak = True
                        perms.connect = True
                        perms.change_nickname = True
                        perms.stream = True
                        await ctx.message.channel.set_permissions(
                            member, overwrite=perms
                        )
                        await ctx.send(
                            f"I have added the following member: {member.name}"
                        )
                        break
                    except Exception as e:
                        await ctx.send(f"I have encountered the following error: {e}")

    @commands.command(
        name="makeprivate",
        help="Make a private channel for you and the supplied members. Note: server owners WILL have access to the "
             "channel as well.",
    )
    @commands.has_any_role("Admins")
    async def make_private_channel(self, ctx, *members: discord.Member):
        try:
            guild = ctx.guild
            creator = ctx.author
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                ),
            }
            channel_name = f"{creator.name}s-private-channel"
            channel = discord.utils.get(guild.text_channels, name=channel_name)

            if channel is None:
                channel = await guild.create_text_channel(
                    channel_name,
                    category=discord.utils.get(ctx.guild.categories, name="🔐 Private"),
                    overwrites=overwrites,
                )
                await ctx.send(f"Channel: {channel} has been created!")
            elif channel:
                await ctx.send(f"Channel: {channel_name} already exists!")
            # whoops add permissions to creater also
            perms = channel.overwrites_for(creator)
            perms.send_messages = True
            perms.read_messages = True
            perms.attach_files = True
            perms.embed_links = True
            perms.read_message_history = True
            perms.mention_everyone = True
            perms.use_external_emojis = True
            perms.attach_files = True
            perms.speak = True
            perms.connect = True
            perms.change_nickname = True
            perms.stream = True
            await channel.set_permissions(creator, overwrite=perms)
            for member in members:
                perms = channel.overwrites_for(member)
                perms.send_messages = True
                perms.read_messages = True
                perms.attach_files = True
                perms.embed_links = True
                perms.read_message_history = True
                perms.mention_everyone = True
                perms.use_external_emojis = True
                perms.attach_files = True
                perms.speak = True
                perms.connect = True
                perms.change_nickname = True
                perms.stream = True
                await channel.set_permissions(member, overwrite=perms)

            await ctx.send(
                f'I have added: {", ".join([member.name for member in members])} to channel'
            )
        except Exception as e:
            await ctx.send(f"I have encountered the following error: {e}")

    @commands.command(
        name="getmyid",
        aliases=["myid"],
        help="Return your discord user ID, helpful for debugging.",
    )
    async def get_my_user_id(self, ctx):
        await ctx.send(f"Your user ID is: {ctx.message.author.id}")

    @commands.command(
        pass_context=True, help="Delete all the messages from this channel."
    )
    @commands.has_role("Admins")
    async def purge(self, ctx, count=None):
        if count is None:
            await ctx.channel.purge()
        else:
            await ctx.channel.purge(limit=int(count))

    @commands.command(name="ip", aliases=["getip"], help="Returns external IP")
    @commands.has_role("Owner")
    async def get_external_ip(self, ctx):
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            ThreadPoolExecutor(), requests.get, "http://api.hostip.info/get_json.php"
        )
        await ctx.send(str(r.json()["ip"]))

    @commands.command(name="troll", help="Boosters only!")
    @commands.has_role("Server Booster")
    async def get_voice_channels(self, ctx):
        if ctx.message.channel.id != self.booster_channel:
            await ctx.send("I don't do such things.")
        else:
            voice_channel_list = ctx.guild.voice_channels
            active_channels = [
                active_channel
                for active_channel in voice_channel_list
                if "Marvin" not in [member.name for member in active_channel.members]
                and len([member.name for member in active_channel.members]) > 0
            ]

            # prioritize joining an active channel otherwise join any channel and wait for someone to join
            if len(active_channels) > 0:
                channel_to_join = random.choice(active_channels)
            else:
                channel_to_join = random.choice(voice_channel_list)

            # now that we have a channel to join, see if we are already in one that we need to disconnect from
            voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            if voice_client:
                await ctx.send(
                    f"Disconnecting from current voice channel and switching to: {channel_to_join.name}"
                )
                await voice_client.disconnect()
                new_channel = await channel_to_join.connect()
            else:
                await ctx.send(f"Attempting to join: {channel_to_join.name}")
                new_channel = await channel_to_join.connect()
            media_file = (
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                + "/assets/media/rroll.mp3"
            )
            new_channel.play(discord.FFmpegPCMAudio(media_file))
            while new_channel.is_playing():
                await asyncio.sleep(1)
            await new_channel.disconnect()


async def setup(bot):
    await bot.add_cog(MarvinBot(bot))
