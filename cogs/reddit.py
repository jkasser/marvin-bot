import praw
from prawcore.exceptions import ServerError, ResponseException
import os
import yaml
import discord
import asyncio
from discord.ext import commands, tasks
from sqlite3 import Error
from utils.db import MarvinDB
from utils.helper import get_current_hour_of_day
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinReddit(MarvinDB, commands.Cog):

    TABLE_NAME = 'reddit'

    REDDIT_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        post_id integer NOT NULL
    );"""

    INSERT_POST = f"""INSERT INTO {TABLE_NAME}(post_id) VALUES(?)"""

    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE post_id=? LIMIT 1)"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__()
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        client_id = cfg["reddit"]["client_id"]
        client_secret = cfg["reddit"]["client_secret"]
        env = os.environ.get('ENV', 'dev')
        self.lol_channel = cfg["disc"][env]["lol_channel"]
        self.travel_channel = cfg["disc"][env]["travel_channel"]
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Marvin Bot 1.0",
        )
        try:
            self.create_table(self.conn, self.REDDIT_TABLE)
        except Error as e:
            print(e)
        self.post_tracker = {"travel_stream": [], "lol_stream": []}
        self.check_reddit_travel_stream.start()
        self.check_reddit_lol_stream.start()

    def get_travel_stream(self, limit=5):
        try:
            submissions = [
                submission for submission in self.reddit.multireddit("OneBagOneWorld",
                                                                     "OneBagOneWorld").top(limit=limit, time_filter="day")
            ]
        except (ServerError, ResponseException):
            submissions = None
        if submissions is not None:
            post_list = self.parse_stream(submissions)
            return post_list

    def parse_stream(self, stream):
        post_list = []
        for submission in stream:
            if not submission.stickied:
                post_id = submission.id
                post_list.append((post_id, submission.title[:250], submission.selftext[:100],
                                  f'https://old.reddit.com{submission.permalink}',
                                  submission.thumbnail, submission.subreddit))
        return post_list

    def get_lol_stream(self, limit=5):
        try:
            submissions = [submission for submission in
                           self.reddit.subreddit("summonerschool+leagueoflegends").top(limit=limit, time_filter="day")]
        except (ServerError, ResponseException):
            submissions = None
        if submissions is not None:
            post_list = self.parse_stream(submissions)
            return post_list

    @tasks.loop(minutes=15)
    async def check_reddit_travel_stream(self):
        try:
            loop = asyncio.get_event_loop()
            travel_channel =  self.bot.get_channel(int(self.travel_channel))
            post_list = await loop.run_in_executor(ThreadPoolExecutor(), self.get_travel_stream)
            if post_list is not None and len(post_list) >= 1:
                for post in post_list:
                    if post[0] in self.post_tracker["travel_stream"]:
                        continue
                    else:
                        embedded_link = discord.Embed(title=post[1], description=post[2], url=post[3], color=0x00ff00)
                        embedded_link.add_field(name="subreddit", value=post[5])
                        if post[4] != 'default' and post[4] != 'self':
                            embedded_link.set_thumbnail(url=post[4])
                        await travel_channel.send(embed=embedded_link)
                        self.post_tracker["travel_stream"].append(post[0])
        except discord.errors.HTTPException:
            pass

    @tasks.loop(minutes=8)
    async def check_reddit_lol_stream(self):
        try:
            loop = asyncio.get_event_loop()
            lol_channel = self.bot.get_channel(int(self.lol_channel))
            post_list = await loop.run_in_executor(ThreadPoolExecutor(), self.get_lol_stream)
            if post_list is not None and len(post_list) >= 1:
                for post in post_list:
                    if post[0] in self.post_tracker["lol_stream"]:
                        continue
                    else:
                        try:
                            embedded_link = discord.Embed(title=post[1], description=post[2], url=post[3], color=0x07f9DA)
                            embedded_link.add_field(name="subreddit", value=post[5])
                            if post[4] != 'default' and post[4] != 'self':
                                embedded_link.set_thumbnail(url=post[4])
                            await lol_channel.send(embed=embedded_link)
                            # finally add it to the DB once it has been sent
                            self.post_tracker["lol_stream"].append(post[0])
                        except Exception:
                            continue
        except discord.errors.HTTPException:
            pass

    @tasks.loop(hours=1)
    async def clear_post_trackers(self):
        hour = get_current_hour_of_day()
        if hour >= 0 and hour <= 1:
            # clear out our lists in memory every 24 hours, check every hour,
            self.post_tracker["lol_stream"].clear()
            self.post_tracker["travel_stream"].clear()

    @check_reddit_lol_stream.before_loop
    async def before_check_reddit_lol_stream(self):
      await self.bot.wait_until_ready()

    @check_reddit_travel_stream.before_loop
    async def before_check_reddit_travel_stream(self):
      await self.bot.wait_until_ready()

    @clear_post_trackers.before_loop
    async def before_clear_post_trackers(self):
        await self.bot.wait_until_ready


def setup(bot):
    bot.add_cog(MarvinReddit(bot))
