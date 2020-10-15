import praw
import yaml
import discord
from discord.ext import commands, tasks
from sqlite3 import Error
from utils.db import MarvinDB


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
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Marvin Bot 1.0 by /u/onebagoneworld",
        )
        try:
            self.create_table(self.conn, self.REDDIT_TABLE)
        except Error as e:
            print(e)
        self.check_reddit_travel_stream.start()
        self.check_reddit_travel_stream.start()

    def add_post_id_to_db(self, post_id):
        self.insert_query(self.INSERT_POST, (post_id,))

    def check_if_post_exists(self, post_id):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS, (post_id,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def get_travel_stream(self, limit=10):
        submissions = [
            submission for submission in self.reddit.multireddit("OneBagOneWorld",
                                                                 "OneBagOneWorld").top(limit=limit, time_filter="day")
        ]
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

    def get_lol_stream(self, limit=10):
        submissions = [submission for submission in
                       self.reddit.subreddit("summonerschool+leagueoflegends").top(limit=limit, time_filter="day")]
        if submissions is not None:
            post_list = self.parse_stream(submissions)
            return post_list

    @tasks.loop(minutes=15)
    async def check_reddit_travel_stream(self):
        try:
            travel_channel = self.bot.get_channel(758126844708651041)
            post_list = self.get_travel_stream(limit=5)
            if len(post_list) >= 1:
                for post in post_list:
                    if self.check_if_post_exists(post[0]):
                        continue
                    else:
                        embedded_link = discord.Embed(title=post[1], description=post[2], url=post[3], color=0x00ff00)
                        embedded_link.add_field(name="subreddit", value=post[5])
                        if post[4] != 'default' and post[4] != 'self':
                            embedded_link.set_thumbnail(url=post[4])
                        await travel_channel.send(embed=embedded_link)
                        await travel_channel.send('---------------------------------------------------------------')
                        # finally add it to the DB once it has been sent
                        self.add_post_id_to_db(post[0])
        except discord.errors.HTTPException:
            pass

    @tasks.loop(minutes=8)
    async def check_reddit_lol_streamself(self):
        lol_channel = self.bot.get_channel(761291587044376598)
        post_list = self.get_lol_stream(limit=5)
        if len(post_list) >= 1:
            for post in post_list:
                if self.check_if_post_exists(post[0]):
                    continue
                else:
                    try:
                        embedded_link = discord.Embed(title=post[1], description=post[2], url=post[3], color=0x07f9DA)
                        embedded_link.add_field(name="subreddit", value=post[5])
                        if post[4] != 'default' and post[4] != 'self':
                            embedded_link.set_thumbnail(url=post[4])
                        await lol_channel.send(embed=embedded_link)
                        await lol_channel.send('---------------------------------------------------------------')
                        # finally add it to the DB once it has been sent
                        self.add_post_id_to_db(post[0])
                    except Exception:
                        continue


def setup(bot):
    bot.add_cog(MarvinReddit(bot))
