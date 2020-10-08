import yaml
import random
import discord
from discord.ext import commands, tasks
from utils.riot import Riot
from utils.reminder import ReminderBot
from utils.reddit import MarvinReddit
from utils.news import MarvinNews
from utils.mapquest import Mapquest
from utils.rapid_api import RapidWeatherAPI
from utils.jeopardy import Jeopardy
from utils.helper import fuzz_compare_answers, update_leaderboard, check_if_user_in_leaderboard, get_current_player_from_leaderboard
import datetime, time
from data.quotes import *


file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
# discord config
token = cfg["disc"]["token"]
intents = discord.Intents().all()
bot = commands.Bot(command_prefix=cfg["disc"]["prefix"], intents=intents)

# set keys here
r_client_id = cfg["reddit"]["client_id"]
r_client_secret = cfg["reddit"]["client_secret"]
open_weather = cfg["rapidAPI"]["key"]
mapquest_token = cfg["mapquest"]["key"]
# Variables in memory
named_queues = {"General": []}
question_list = []
leaderboard = []


# Instantiate Objects here
jep = Jeopardy()
rito = Riot()
reminder = ReminderBot()
reddit_feed = MarvinReddit(r_client_id, r_client_secret)
news_bot = MarvinNews(cfg["news"]["key"])
mapq = Mapquest(mapquest_token)
weather_api = RapidWeatherAPI(open_weather)


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    print(f'We have logged in as {bot.user}')  # notification of login.
    standings = jep.get_leaderboard()
    for standing in standings:
        leaderboard.append({standing[1]: f'${standing[2]}'})
    update_jep_leaderboard.start()
    check_reddit_lol_stream.start()
    check_reddit_travel_stream.start()
    check_the_news.start()
    check_and_update_latest_assets_version.start()
    get_rito_status.start()
    check_for_reminders.start()


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


@bot.command(name='marvin', help='Check in on Marvin the depressed robot!')
async def marvin_quote(ctx):
    response = random.choice(marvin_quotes)
    await ctx.send(response)


@bot.command(name='grail', help='Tis a silly command')
async def get_monty_python_quotes(ctx):
    response = random.choice(holy_grail_quotes)
    await ctx.send(response)


@bot.command(name='lullaby', help='Let Marvin read you a lullaby!')
async def post_marvin_lullaby(ctx):
    await ctx.send(marvin_lullaby)


@bot.command(name='flipcoin', help='Having trouble making a decision? Let Marvin flip a coin for you!')
async def marvin_coin_flip(ctx):
    coin_choices = ['Heads', 'Tails']
    await ctx.send(f'Results are in!\nThe coin landed on: {random.choice(coin_choices)}')


@bot.command(name='clash', help='Get current and upcoming clash tournament schedule.')
async def get_clash(ctx):
    schedule = rito.get_clash_schedule()
    await ctx.send(str(schedule))


@bot.command(name='whatsmyvibe', help='What you vibing too right now lil gangsta?')
async def get_vibe(ctx, user: discord.Member=None):
    user = user or ctx.author  # default to the caller
    spot = next((activity for activity in user.activities if isinstance(activity, discord.Spotify)), None)
    if spot is None:
        await ctx.send(f"{user.name.capitalize()} is not listening to Spotify.")
        return
    embedspotify = discord.Embed(title=f"{user.name}'s Spotify", color=0x1eba10)
    embedspotify.add_field(name="Song", value=spot.title, inline=False)
    embedspotify.add_field(name="Artist", value=spot.artist, inline=False)
    embedspotify.add_field(name="Album", value=spot.album)
    embedspotify.set_thumbnail(url=spot.album_cover_url)
    await ctx.send(embed=embedspotify)


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
    now = datetime.datetime.now()
    user = user or ctx.author
    channel_id = ctx.message.channel.id
    try:
        # parse the string into 3 fields to insert into the databse
        name, when, what = reminder.parse_reminder_text(text)
        if name.lower() == 'me':
            name = '@' + user.mention
        # get the date as a datetime object
        when_datetime = reminder.get_when_remind_date(when, start_time=now)
        # now insert it into the db
        reminder.insert_reminder((name, when_datetime, what, channel_id))
        await ctx.send(f'I will remind {name} - "{what}" at {when_datetime.astimezone().strftime("%a, %b %d, %Y %I:%M:%S, %Z")}')
    except ValueError:
        await ctx.send('ERROR: Reminder was in an invalid format! Please use: !remind <who> in|on <when> to|that <what>.\nDo not spell out numbers. Years and Months must be whole numbers.\nWho must come first, when/what can come in either order.')


@bot.command(name='adduser', help="Add a user to the channel. You must be a member of TheOGs to use this command.")
@commands.has_any_role("Admins", "TheOGs")
async def add_user_to_channel(ctx, * users):
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


@bot.command(name='makeprivate', help="Make a private channel for you and x members")
@commands.has_any_role("Admins", "TheOGs")
async def make_private_channel(ctx, * members:discord.Member):
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
            channel = await guild.create_text_channel(channel_name, category=discord.utils.get(ctx.guild.categories, name='private'), overwrites=overwrites)
            await ctx.send(f'Channel: {channel} has been created!')
        elif channel:
            await ctx.send(f'Channel: {channel_name} already exists!')
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


@bot.command(name='qcreate', help="Create a single word named queue in memory, if left blank, will create the 'General' queue, which exists by default.\nEx. !qcreate myqueue")
@commands.has_any_role("Admins", "TheOGs")
async def create_named_queue(ctx, name='General'):
    if name not in named_queues.keys():
        named_queues[name] = []
        await ctx.send(f'Queue: {name}, created!')
    else:
        await ctx.send(f'Queue: {name}, already exists!')


@bot.command(name='qaddme', help="Call !qaddme <name> to be added to a specific queue, if name is not provided it adds you to the general queue.\nEx. !qaddme myqueue")
async def add_me_to_queue(ctx, name=None):
    if name is None:
        queue = named_queues["General"]
        name = 'General'
    else:
        if name in named_queues.keys():
            queue = named_queues[name]
        else:
            await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
            return
    username = ctx.author.mention
    queue.append(username)
    await ctx.send(f'{username} has been added to the: {name} queue at position: {queue.index(username)+1}')


@bot.command(name='qadduser', help="This only works to add a user to the general queue, pass in the user\'s username.\nEx. !adduser marvin")
@commands.has_any_role("Admins", "TheOGs")
async def add_user_to_queue(ctx, user):
    queue = named_queues["General"]
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


@bot.command(name='qlist', help="See the current queue list of the queue name provided. If no name is provided then it will provide the list of the General queue.\nEx. !qlist myqueue")
async def get_queue_list(ctx, name=None):
    if name is None:
        queue = named_queues["General"]
        name = 'General'
    else:
        if name in named_queues.keys():
            queue = named_queues[name]
        else:
            await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
            return
    if len(queue) >= 1:
        await ctx.send(f'{", ".join(user for user in queue)}')
    else:
        await ctx.send(f'The {name} queue is currently empty.')


@bot.command(name='qclear', help="Clears the provided queue name. If no queue name is provided it will clear the General queue.\nEx. !qclear myqueue")
@commands.has_any_role("Admins", "TheOGs")
async def clear_queue(ctx, name=None):
    if name is None:
        queue = named_queues["General"]
        name = 'General'
    else:
        if name in named_queues.keys():
            queue = named_queues[name]
        else:
            await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
            return
    queue.clear()
    await ctx.send(f'The queue: {name} has been cleared!')


@bot.command(name='qnext', help="Call the next person in the provided queue. If no queue name is provided, it will call the next person from the General queue.\nEx. !qnext myqueue")
@commands.has_any_role("Admins", "TheOGs")
async def get_next_user_in_queue(ctx, name=None):
    if name is None:
        queue = named_queues["General"]
        name = 'General'
    else:
        if name in named_queues.keys():
            queue = named_queues[name]
        else:
            await ctx.send(f'The {name} queue does not currently exist! Use !qcreate <name> to create it!')
            return

    if len(queue) >= 1:
        user = queue.pop(0)
        await ctx.send(f'{user}, you have been summoned!')
    else:
        await ctx.send(f'The {name} queue is empty! There is no one else to call')


@bot.command(name='getmyid', help="Return your discord user ID, helpful for debugging.")
async def get_my_user_id(ctx):
    await ctx.send(f'Your user ID is: {ctx.message.author.id}')


@bot.command(pass_context=True, help="Delete all the messages from this channel")
@commands.has_any_role("Admins")
async def purge(ctx):
    await ctx.channel.purge()


@bot.command(name='getnewssources', help="See where I pull my news from!")
async def get_news_sources(ctx):
    await ctx.send(f'I get my news from the following sources: {", ".join(cfg["news"]["sources"]).replace("-", " ").capitalize()}')


@bot.command(name='getnews', help="Get the top 3 articles for your keyword! Please wrap multiple words in quotes.")
async def get_news_for_keyword(ctx, query):
    news_list = news_bot.get_news(q=query)
    if isinstance(news_list, list):
        for article in news_list:
            try:
                embedded_link = discord.Embed(title=article["title"], description=article["description"],
                                              url=article["url"])
                embedded_link.add_field(name="Source", value=article["source"], inline=True)
                embedded_link.add_field(name="Author", value=article["author"], inline=True)
                embedded_link.add_field(name="Published", value=article["published"], inline=True)
                if article["thumb"] is not "" and article["thumb"] is not None:
                    embedded_link.set_thumbnail(url=article["thumb"])
                await ctx.send(embed=embedded_link)
                await ctx.send('---------------------------------------------------------------')
                news_bot.add_article_to_db(article["article_slug"])
            except Exception:
                continue
    else:
        await ctx.send(f'I wasn\'t able to find anything for: {query}!')


@bot.command(name='playjep', help="Play a round of jeopardy!")
async def play_jeopardy(ctx):
    current_player = ctx.author.name
    timeout = 60
    # Once we get to 5 questions left, retrieve another 20, store them in memory
    if len(question_list) <= 5:
        questions = jep.get_questions()
        for question in questions:
            question_dict = {
                "id": question[0],
                "category": question[1],
                "question": jep.parse_question(question[2]),
                "worth": question[3],
                "answer": question[4]
            }
            question_list.append(question_dict)
    # create a new contestant or welcome someone back
    await ctx.send('This is Marvinpardy!\nAnd here is your host... Me! A clinically depressed robot!')
    if len(leaderboard) != 0:
        if check_if_user_in_leaderboard(leaderboard, current_player):
            worth = get_current_player_from_leaderboard(leaderboard, current_player)
            await ctx.send(f'I see you are back for more {current_player}!\nYour current worth is: {worth}')
        else:
            await ctx.send('Welcome new contestant!')
            leaderboard.append({current_player: "$0"})
    else:
        await ctx.send('Welcome new contestant!')
        leaderboard.append({current_player: "$0"})

    # now ask a random question
    question_to_ask = random.choice(question_list)
    await ctx.send(f'Category: **{question_to_ask["category"]}**\nValue: **{question_to_ask["worth"]}**\nQuestion: **{question_to_ask["question"]}**')
    await ctx.send(f'You have **{timeout}** seconds to answer starting now!')
    # remove the question from the list in memory
    question_list.pop(question_list.index(question_to_ask))
    # await for the response and check the answer
    def check(m):
        return m.author.name == ctx.author.name
    user_answer = await bot.wait_for("message", check=check, timeout=timeout)
    correctness = fuzz_compare_answers(question_to_ask["answer"], user_answer.content)
    await ctx.send(f'The correct answer is: **{question_to_ask["answer"]}**\nYou answered: **{user_answer.content}**')
    await ctx.send(f'Your answer is: **{correctness}%** correct.')
    # determine correctness and update leaderboard, polling task will update scores in the DB every 5 minutes
    if correctness >= 60:
        await ctx.send(f'We will consider that a valid answer, you have just earned {question_to_ask["worth"]}')
        new_worth = update_leaderboard(leaderboard, current_player, question_to_ask["worth"])
        await ctx.send(f'Your worth is now: {new_worth}')
    else:
        await ctx.send(f'That was not correct!')
        lost_worth = f'$-{question_to_ask["worth"].split("$")[1]}'
        new_worth = update_leaderboard(leaderboard, current_player, lost_worth)
        await ctx.send(f'Your worth is now: {new_worth}')


@bot.command('jepstandings', help="See the current standings!")
async def get_jep_standings(ctx):
    await ctx.send(f'**Player**: **Worth**')
    for standing in leaderboard:
        for player, worth in standing.items():
            await ctx.send(f'{player}: {worth}')



@tasks.loop(seconds=500)
async def update_jep_leaderboard():
    for standing in leaderboard:
        for player,value in standing.items():
            # check if player exists in db
            if jep.check_if_player_exists(player):
                jep.update_player_score(value, player)
            # if they don't insert player and then update:
            else:
                jep.insert_player(player, value)


@bot.command(name='getsummoner', help="Pass in a summoner name and to get their info!")
async def get_summoner(ctx, summoner_name):
    summoner_name = summoner_name.lower()
    results = rito.get_summoner_by_name(summoner_name)
    if results is None:
        try:
            name, summoner_level, profile_icon_id = rito.get_and_update_summoner_from_riot_by_name(summoner_name)
        # this will return None if no results are found which raises a type error
        except TypeError:
            await ctx.send(f'Summoner: {summoner_name} was not found! Make sure you have the spelling correct!')
            return
    else:
        one_day_ago = int(str(time.time()).replace('.', '')[:len(str(results[7]))]) - 86400
        if results[7] <= one_day_ago:
            # its been awhile, let's get new info
            name, summoner_level, profile_icon_id = rito.get_and_update_summoner_from_riot_by_name(summoner_name)
        else:
            name, summoner_level, profile_icon_id = results[1], results[5], results[6]
    embedded_link = discord.Embed(title=name, description=summoner_level, color=0x8b0000)
    # Get the summoner icon
    file = discord.File(rito.get_profile_img_for_id(profile_icon_id), filename=f'{profile_icon_id}.png')
    embedded_link.set_image(url=f'attachment://{profile_icon_id}.png')
    await ctx.send(file=file, embed=embedded_link)


@bot.command(name='updatesummoner', help="Pass in a summoner name to update them in the databse")
async def update_summoner(ctx, summoner_name):
    summoner_name = summoner_name.lower()
    try:
        name, summoner_level, profile_icon_id = rito.get_and_update_summoner_from_riot_by_name(summoner_name)
    except TypeError:
        await ctx.send(f'Summoner: {summoner_name} was not found! Make sure you have the spelling correct!')
        return
    embedded_link = discord.Embed(title=name, description=summoner_level, color=0x8b0000)
    # Get the summoner icon
    file = discord.File(rito.get_profile_img_for_id(profile_icon_id), filename=f'{profile_icon_id}.png')
    embedded_link.set_image(url=f'attachment://{profile_icon_id}.png')
    await ctx.send(file=file, embed=embedded_link)


@bot.command(name='getweather', help="Provide city/state/country/zip to get today's weather forecast!")
async def get_todays_weather(ctx, query):
    if query is not None:
        results = mapq.get_lat_long_for_location(str(query))
        forecast = weather_api.get_daily_weather_for_city(lat=results["lat"], long=results["long"])
        if forecast is not None:
            embed = discord.Embed(title=f"Weather in {query}",
                                  color=0x87ceeb,
                                  timestamp=ctx.message.created_at, )
            embed.add_field(name="Description", value=f"**{forecast['type']}**", inline=False)
            embed.add_field(name="Temperature(F)", value=f"**{forecast['temp']}°F**", inline=False)
            embed.add_field(name="Feels Like(F)", value=f"**{forecast['feels_like']}°F**", inline=False)
            embed.add_field(name="Min Temp(F)", value=f"**{forecast['min']}°F**", inline=False)
            embed.add_field(name="Max Temp(F)", value=f"**{forecast['max']}°F**", inline=False)
            embed.add_field(name="Humidity(%)", value=f"**{forecast['humidity']}%**", inline=False)
            embed.add_field(name="Wind(MPH)", value=f"**{forecast['wind']}MPH**", inline=False)
            embed.set_thumbnail(url=results["thumb"])
            embed.set_footer(text=f"Requested by {ctx.author.name}")
            await ctx.send(embed=embed)
    else:
        await ctx.send('Please provide a city/state or zip code.')

#### Task Loops start here ####

@tasks.loop(seconds=600)
async def check_reddit_travel_stream():
    try:
        travel_channel = bot.get_channel(758126844708651041)
        post_list = reddit_feed.get_travel_stream(limit=5)
        if len(post_list) >= 1:
            for post in post_list:
                if reddit_feed.check_if_post_exists(post[0]):
                    continue
                else:
                    embedded_link = discord.Embed(title=post[1], description=post[2],  url=post[3], color=0x00ff00)
                    embedded_link.add_field(name="subreddit", value=post[5])
                    if post[4] != 'default' and post[4] != 'self':
                        embedded_link.set_thumbnail(url=post[4])
                    await travel_channel.send(embed=embedded_link)
                    await travel_channel.send('---------------------------------------------------------------')
                    # finally add it to the DB once it has been sent
                    reddit_feed.add_post_id_to_db(post[0])
    except discord.errors.HTTPException:
        pass


@tasks.loop(seconds=600)
async def check_reddit_lol_stream():
    lol_channel = bot.get_channel(761291587044376598)
    post_list = reddit_feed.get_lol_stream(limit=5)
    if len(post_list) >= 1:
        for post in post_list:
            if reddit_feed.check_if_post_exists(post[0]):
                continue
            else:
                try:
                    embedded_link = discord.Embed(title=post[1], description=post[2],  url=post[3], color=0x07f9DA)
                    embedded_link.add_field(name="subreddit", value=post[5])
                    if post[4] != 'default' and post[4] != 'self':
                        embedded_link.set_thumbnail(url=post[4])
                    await lol_channel.send(embed=embedded_link)
                    await lol_channel.send('---------------------------------------------------------------')
                    # finally add it to the DB once it has been sent
                    reddit_feed.add_post_id_to_db(post[0])
                except Exception:
                    continue


@tasks.loop(hours=1)
async def check_the_news():
    news_channel = bot.get_channel(761691682383069214)
    sources = ",".join(cfg["news"]["sources"])
    news_list = news_bot.news.get_top_headlines(page_size=3, sources=sources)["articles"]
    if isinstance(news_list, list):
        for post in news_list:
            # parse the article
            article = news_bot.get_article_data(post)
            # check if the news has already been posted
            if news_bot.check_if_article_exists(news_bot.get_article_slug(article["article_slug"])):
                continue
            else:
                try:
                    embedded_link = discord.Embed(title=article["title"], description=article["description"], url=article["url"])
                    embedded_link.add_field(name="Source", value=article["source"], inline=True)
                    embedded_link.add_field(name="Author", value=article["author"], inline=True)
                    embedded_link.add_field(name="Published", value=article["published"], inline=True)
                    if article["thumb"] is not "" and article["thumb"] is not None:
                        embedded_link.set_thumbnail(url=article["thumb"])
                    await news_channel.send(embed=embedded_link)
                    await news_channel.send('---------------------------------------------------------------')
                    news_bot.add_article_to_db(article["article_slug"])
                except Exception:
                    continue
    else:
        await news_channel.send('I wasn\'t able to find any news!')


@tasks.loop(hours=1)
async def check_and_update_latest_assets_version():
    if datetime.datetime.now().hour >= 23 and datetime.datetime.now().hour <= 6:
        api_updates_channel = bot.get_channel(763088226860138576)
        api_current_version, cdn = rito.get_latest_data_version()
        if rito.check_if_assets_current_version_exists():
            assets_db_version = rito.get_current_assets_version_from_db()[0]
            # See if the api version is greater than our current one
            if int(''.join(api_current_version.split('.'))) > int(''.join(assets_db_version.split('.'))):
                await api_updates_channel.send(f'Our current version: {assets_db_version} is out of date!\nDownloading latest version: {api_current_version}')
                # Update our local assets
                rito.download_new_assets(cdn, api_current_version)
                # Now Update it in the DB
                rito.update_assets_current_version(current_version=api_current_version)
                await api_updates_channel.send(f'We are now using LoL assets version: {api_current_version}')
            # otherwise if they are equal then just say we are on the most current version
            elif int(''.join(api_current_version.split('.'))) == int(''.join(assets_db_version.split('.'))):
                await api_updates_channel.send(f'We are on the most current LoL assets version: {assets_db_version}')
                return
        else:
            # If the field doesn't exist then download the latest version
            rito.download_new_assets(cdn, api_current_version)
            # update our local assets
            # Add it to the DB
            rito.insert_assets_current_version(api_current_version)
            await api_updates_channel.send(f'We are now using LoL assets version: {api_current_version}')


@tasks.loop(minutes=5)
async def get_rito_status():
    status_channel = bot.get_channel(763153164798394378)
    issues = rito.get_and_parse_riot_status_issues()
    if len(issues) > 0:
        for x in issues:
            if rito.check_if_issue_hash_exists(x["hash"]):
                continue
            else:
                if x["severity"] == "info":
                    color = 0xf8d568
                else:
                    color = 0xff0000
                embedded_link = discord.Embed(title=x["title"], description=x["updates"], color=color)
                embedded_link.add_field(name="created", value=x["created"])
                await status_channel.send(embed=embedded_link)
                rito.insert_issue_hash(x["hash"])



@tasks.loop(seconds=10)
async def check_for_reminders():
    results = reminder.check_reminders()
    if len(results):
        # results are a tuple of index, name, when, what, channel_id, and sent
        for result in results:
            # check the when date to see if its => now
            if datetime.datetime.now() >= result[2]:
                channel = bot.get_channel(result[4])
                await channel.send(f'{result[1]}! This is your reminder to: {result[3]}!')
                # set it as sent
                reminder.mark_reminder_sent(result[0])



@bot.event
async def on_command_error(ctx, error):
    await ctx.send(error)


if __name__ == '__main__':
    bot.run(token)
