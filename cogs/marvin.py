import discord
import random
from data.quotes import *
from discord.ext import commands


class MarvinBot(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.named_queues = dict(General=[])

    @commands.command(name='marvin', help='Check in on Marvin the depressed robot!')
    async def marvin_quote(self, ctx):
        response = random.choice(marvin_quotes)
        await ctx.send(response)

    @commands.command(name='grail', help='Tis a silly command')
    async def get_monty_python_quotes(self, ctx):
        response = random.choice(holy_grail_quotes)
        await ctx.send(response)

    @commands.command(name='kanye', aliases=['yeezy', 'yeezus'],
                      help='Whipped it out she said I never seen snakes on a plane.')
    async def get_kanye_quotes(self, ctx):
        response = random.choice(kanye_quotes)
        await ctx.send(response)

    @commands.command(name='lullaby', help='Let Marvin read you a lullaby!')
    async def post_marvin_lullaby(self, ctx):
        await ctx.send(marvin_lullaby)

    @commands.command(name='flipcoin', help='Having trouble making a decision? Let Marvin flip a coin for you!')
    async def marvin_coin_flip(self, ctx):
        coin_choices = ['Heads', 'Tails']
        await ctx.send(f'Results are in!\nThe coin landed on: {random.choice(coin_choices)}')

    @commands.command(name='whatsmyvibe', help='What you vibing too right now lil gangsta?')
    async def get_vibe(self, ctx, user: discord.Member = None):
        base_url = 'https://open.spotify.com/track/'
        user = user or ctx.author  # default to the caller
        spot = next((activity for activity in user.activities if isinstance(activity, discord.Spotify)), None)
        if spot is None:
            await ctx.send(f"{user.name.capitalize()} is not listening to Spotify.")
            return
        embedspotify = discord.Embed(title=f"{user.name}'s Spotify", color=0x1eba10, url=base_url+spot.track_id)
        embedspotify.add_field(name="Song", value=spot.title, inline=False)
        embedspotify.add_field(name="Artist", value=spot.artist, inline=False)
        embedspotify.add_field(name="Album", value=spot.album)
        embedspotify.set_thumbnail(url=spot.album_cover_url)
        await ctx.send(embed=embedspotify)

    @commands.command(name='roll', help='Type !roll <max number> to get a random number between 0 and the max!')
    async def roll_dice(self, ctx, max_roll):
        await ctx.send(f'You rolled {random.randint(0, int(max_roll))}')

    @commands.command(name='decide', help='Let marvin make a decision for you!')
    async def decide(self, ctx):
        await ctx.send(f'{random.choice(["Yes.", "No."])}')

    @commands.command(name='hangover', help='Get some medical advice from someone completely unqualified!')
    async def hangover(self, ctx):
        await ctx.send(random.choice(hangover_cures))

    @commands.command(name='addrole', pass_context=True)
    @commands.has_any_role("Admins", "TheOGs")
    async def add_role_to_user(self, ctx, user: discord.Member, role: discord.Role):
        await user.add_roles(role)
        await ctx.send(f'{ctx.author.name} has bestowed the role of {role.name} on {user.display_name}')

    @commands.command(name='removerole', pass_context=True)
    @commands.has_any_role("Admins", "TheOGs")
    async def remove_role_from_user(self, ctx, user: discord.Member, role: discord.Role):
        await user.remove_roles(role)
        await ctx.send(f'{ctx.author.name} has removed the role of {role.name} from {user.display_name}')

    @commands.command(name='getroles')
    async def get_all_roles_in_channel(self, ctx):
        await ctx.send(", ".join([str(r.name) for r in ctx.guild.roles]))

    @commands.command(name='adduser',
                      help='Add a user to the channel. You must be a member of TheOGs to use this command.')
    @commands.has_any_role("Admins", "TheOGs")
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
                        await ctx.message.channel.set_permissions(member, overwrite=perms)
                        await ctx.send(f'I have added the following member: {member.name}')
                        break
                    except Exception as e:
                        await ctx.send(f'I have encountered the following error: {e}')

    @commands.command(name='makeprivate', help='Make a private channel for you and the supplied members.')
    @commands.has_any_role("Admins", "TheOGs")
    async def make_private_channel(self, ctx, * members: discord.Member):
        try:
            guild = ctx.guild
            creator = ctx.author
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            channel_name = f'{creator.name}s-private-channel'
            channel = discord.utils.get(guild.text_channels, name=channel_name)

            if channel is None:
                channel = await guild.create_text_channel(channel_name,
                                                          category=discord.utils.get(ctx.guild.categories,
                                                                                     name='🔐 Private'),
                                                          overwrites=overwrites)
                await ctx.send(f'Channel: {channel} has been created!')
            elif channel:
                await ctx.send(f'Channel: {channel_name} already exists!')
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

            await ctx.send(f'I have added: {", ".join([member.name for member in members])} to channel')
        except Exception as e:
            await ctx.send(f'I have encountered the following error: {e}')

    @commands.command(name='qcreate', aliases=['createq', 'queuecreate', 'createqueue'],
                      help='Create a single word named queue in memory, if left blank, will create the "General"'
                           'queue, which exists by default.\nEx. !qcreate myqueue')
    @commands.has_any_role("Admins", "TheOGs")
    async def create_named_queue(self, ctx, name='General'):
        if name not in self.named_queues.keys():
            self.named_queues[name] = []
            await ctx.send(f'Queue: {name}, created!')
        else:
            await ctx.send(f'Queue: {name}, already exists!')

    @commands.command(name='qaddme', help='Call !qaddme <name> to be added to a specific queue, '
                                     'if name is not provided it adds you to the general queue.\nEx. !qaddme myqueue.')
    async def add_me_to_queue(self, ctx, name=None):
        if name is None:
            queue = self.named_queues["General"]
            name = 'General'
        else:
            if name in self.named_queues.keys():
                queue = self.named_queues[name]
            else:
                await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
                return
        username = ctx.author.mention
        queue.append(username)
        await ctx.send(f'{username} has been added to the: {name} queue at position: {queue.index(username) + 1}')

    @commands.command(name='qadduser', aliases=['qadd', 'queueadd'], help='This only works to add a user to the general queue, '
                                       'pass in the user\'s username.\nEx. !adduser marvin.')
    @commands.has_any_role("Admins", "TheOGs")
    async def add_user_to_queue(self, ctx, user):
        queue = self.named_queues["General"]
        if user is None:
            username = ctx.message.author.mention
            queue.append(username)
            await ctx.send(f'{username} has been added to the General queue at position: {queue.index(username) + 1}')
        else:
            members = await ctx.guild.fetch_members(limit=150).flatten()
            for member in members:
                if user in member.name:
                    username = member.mention
                    queue.append(username)
                    await ctx.send(
                        f'{username} has been added to the General queue at position: {queue.index(username) + 1}')
                    break
                elif members.index(member) + 1 == len(members) and user not in member.name:
                    await ctx.send(f'No member found for {user}')

    @commands.command(name='qlist', aliases=['listq', 'listqueue', 'queuelist'], help='See the current queue list of the queue name provided.'
                                    ' If no name is provided then it will provide the list of the General queue.'
                                    '\nEx. !qlist myqueue')
    async def get_queue_list(self, ctx, name=None):
        if name is None:
            queue = self.named_queues["General"]
            name = 'General'
        else:
            if name in self.named_queues.keys():
                queue = self.named_queues[name]
            else:
                await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
                return
        if len(queue) >= 1:
            await ctx.send(f'{", ".join(user for user in queue)}')
        else:
            await ctx.send(f'The {name} queue is currently empty.')

    @commands.command(name='qclear', aliases=['clearqueue', 'clearq'], help='Clears the provided queue name. If no queue name is provided it will '
                                     'clear the General queue.\nEx. !qclear myqueue')
    @commands.has_any_role("Admins", "TheOGs")
    async def clear_queue(self, ctx, name=None):
        if name is None:
            queue = self.named_queues["General"]
            name = 'General'
        else:
            if name in self.named_queues.keys():
                queue = self.named_queues[name]
            else:
                await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
                return
        queue.clear()
        await ctx.send(f'The queue: {name} has been cleared!')

    @commands.command(name='qnext', aliases=['queuenext', 'next'], help='Call the next person in the provided queue. If no queue name is provided, '
                                    'it will call the next person from the General queue.\nEx. !qnext myqueue')
    @commands.has_any_role("Admins", "TheOGs")
    async def get_next_user_in_queue(self, ctx, name=None):
        if name is None:
            queue = self.named_queues["General"]
            name = 'General'
        else:
            if name in self.named_queues.keys():
                queue = self.named_queues[name]
            else:
                await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
                return

        if len(queue) >= 1:
            user = queue.pop(0)
            await ctx.send(f'{user}, you have been summoned!')
        else:
            await ctx.send(f'The {name} queue is empty! There is no one else to call')

    @commands.command(name='getmyid', aliases=['myid'], help='Return your discord user ID, helpful for debugging.')
    async def get_my_user_id(self, ctx):
        await ctx.send(f'Your user ID is: {ctx.message.author.id}')

    @commands.command(pass_context=True, help='Delete all the messages from this channel.')
    @commands.has_any_role("Admins")
    async def purge(self, ctx, count=None):
        if count is None:
            await ctx.channel.purge()
        else:
            await ctx.channel.purge(limit=int(count))
        

def setup(bot):
    bot.add_cog(MarvinBot(bot))
