import requests
import os
import yaml
from discord.ext import commands, tasks
from utils.db import MarvinDB
from sqlite3 import Error
import asyncio
from asyncio import TimeoutError
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinTube(commands.Cog, MarvinDB):

    MARVIN_TUBE_TABLE = 'video_subs'

    TUBE_TABLE = f"""CREATE TABLE IF NOT EXISTS {MARVIN_TUBE_TABLE} (
        id integer PRIMARY KEY,
        channel_id text NOT NULL,
        channel_title text NOT NULL,
        latest_vid text NOT NULL,
        active integer NOT NULL
    );"""

    INSERT_VIDEO_SUB = f"""INSERT INTO {MARVIN_TUBE_TABLE}(channel_id,channel_title,latest_vid,active) VALUES(?,?,?,?)"""

    UPDATE_SUB_LATEST_VID = f"""UPDATE {MARVIN_TUBE_TABLE} SET latest_vid = ? where id = ?"""
    UPDATE_SUB_ACTIVE_STATUS = f"""UPDATE {MARVIN_TUBE_TABLE} SET active = ? where id = ?"""

    GET_ALL_SUBS = f"""SELECT * FROM {MARVIN_TUBE_TABLE}"""

    def __init__(self, bot):
        super(MarvinTube, self).__init__()
        self.bot = bot
        # try to create the table
        try:
            self.create_table(self.conn, self.TUBE_TABLE)
        except Error as e:
            print(e)
        env = os.environ.get('ENV', 'NOT SET')
        with open('config.yaml', 'r') as file:
            cfg = yaml.safe_load(file)
        self.google_api_key = cfg["google"]["api_key"]
        self.base_url = 'https://www.googleapis.com/youtube/v3/'
        self.channels_endpoint = 'channels'
        self.headers = {
            'Accept': 'application/json'
        }
        self.tv_channel_id = cfg["disc"][env]["video_channel"]
        # get the tables from the db
        subs = self._get_current_subs()
        self.channels = {}
        for sub in subs:
            self.channels[sub[1]] = dict(
                id=sub[0],
                channel_title=sub[2],
                latest_vide=sub[3],
                active=sub[4]
            )
        # start the loop to post videos
        self.check_for_new_videos.start()
        self.insert_or_update_subs_in_db.start()

    def _get_latest_video_for_channel_id(self, channel_id):
        latest_vid = {}
        r = requests.get(
            self.base_url+f'search?key={self.google_api_key}&channelId={channel_id}&order=date&maxResults=1&part=snippet'
        )
        if r.status_code == 200:
            # all the returned videos will be stored in the items list of dicts
            for video in r.json()["items"]:
                latest_vid["channel_title"] = video["snippet"]["channelTitle"]
                latest_vid["video_id"] = video["id"]["videoId"]
                latest_vid["title"] = video["snippet"]["title"]
            return latest_vid
        elif r.status_code == 400:
            # someone could have searched by a custom URL, so try to get fancy and let us search by the name
            r = requests.get(
                self.base_url + f'search?key={self.google_api_key}&order=date&maxResults=1&part=snippet,id&type=channel'
                                f'&q={channel_id}'
            )
            if r.status_code == 200:
                for video in r.json()["items"]:
                    latest_vid["channel_title"] = video["snippet"]["channelTitle"]
                    latest_vid["video_id"] = video["id"]["videoId"]
                    latest_vid["title"] = video["snippet"]["title"]
                return latest_vid

        response = f'There was an error returning this request: {r.status_code}\n{r.text}'
        return response

    # DB methods here
    def _get_current_subs(self):
        results = self.get_query(self.GET_ALL_SUBS)
        return results

    def _insert_sub(self, channel_id: str, channel_title: str, latest_vid: str, active: int):
        return self.insert_query(self.INSERT_VIDEO_SUB, (channel_id, channel_title, latest_vid, active,))

    def _update_latest_vid_for_channel_sub(self, sub_id: int, latest_vid: str):
        self.update_query(self.UPDATE_SUB_LATEST_VID, (latest_vid, sub_id,))

    def _update_sub_active_status(self, sub_id: int, active: int):
        self.update_query(self.UPDATE_SUB_ACTIVE_STATUS, (active, sub_id,))

    @commands.command(name='getchannelsubs', help='Get a list of what youtube channels you are currently subscribed to!')
    async def get_channel_subs(self, ctx):
        new_line = '\n'
        print(self.channels)
        list_of_current_channels = [values["channel_title"] for channel, values in self.channels.items()]
        await ctx.send(f'You are currently subscribed to: {new_line.join(list_of_current_channels)}')

    @commands.command(name='subchannel', help='Subscribe to a youtube channel and have their latest videos posted'
                                              'to our tv channel!')
    async def sub_channel(self, ctx, channel_id=None):
        timeout = 60
        def check(m):
            return m.author.name == ctx.author.name
        if channel_id is None:
            await ctx.send('You haven\'t provided me with a channel ID, could you grab that for me now?')
            try:
                user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
                user_answer = user_answer.content
                if user_answer is not None:
                    await ctx.send(f'Thanks! I will now try to subscribe to: {user_answer}')
                    channel_id = user_answer
            except TimeoutError:
                await ctx.send('You have taken too long to decide! Good-bye!')
                return

        if channel_id not in self.channels.keys():
            disc_channel = self.bot.get_channel(int(self.tv_channel_id))
            # this is the first time we are retrieving this so let's do the whole shebang
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(ThreadPoolExecutor(),
                                                  self._get_latest_video_for_channel_id, channel_id)
            if isinstance(response, dict):
                self.channels[channel_id] = {
                    "active": 1,
                    "latest_vid": response["video_id"],
                    "channel_title": response["channel_title"]
                }
                # let's try to grab the channel name at this point
                await ctx.send(f'Got it! We are now subscribed to \"{response["channel_title"]}\".\nPosting their latest'
                               f' video now!')
                await disc_channel.send(f'https://youtube.com/watch?v={response["video_id"]}')
            else:
                # if its not a dict we got a string back which means the API call failed, post the error to the channel
                await ctx.send(response)
        else:
            await ctx.send(f'You are already subbed to {self.channels[channel_id]["channel_title"]}')


    @tasks.loop(minutes=30)
    async def check_for_new_videos(self):
        disc_channel = self.bot.get_channel(int(self.tv_channel_id))
        loop = asyncio.get_event_loop()
        for channel_id, channel_values in self.channels.items():
            # only grab active channel subscriptions
            if channel_values["active"]:
                # check channel k here, see if latest v == the latest channel
                response = await loop.run_in_executor(ThreadPoolExecutor(), self._get_latest_video_for_channel_id(channel_id))
                if isinstance(response, dict):
                    latest_video = response["video_id"]
                    if channel_values["latest_vid"] == latest_video:
                        continue
                    else:
                        # update the latest video id we have and post it to the channel
                        channel_values["latest_vid"] = latest_video
                        await disc_channel.send(f'https://youtube.com/watch?v={latest_video}')
                        # set an update flag on the record in the dictionary so we know to update the DB
                        channel_values["update_pending"] = True
                else:
                    # if its not a dict we got a string back which means the API call failed, post the error to the channel
                    await disc_channel.send(response)
                    await disc_channel.send(f'Setting the subscription for \"{channel_values["channel_title"]}\" to '
                                                 f'inactive')
                    # set the channel to inactive
                    channel_values["active"] = 0
                    # set an update flag on the record in the dictionary so we know to update the DB
                    channel_values["update_pending"] = True

    @check_for_new_videos.before_loop
    async def before_check_for_new_videos(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=15)
    async def insert_or_update_subs_in_db(self):
        for channel_id, channel_values in self.channels.items():
            # if the ID isnt in the keys then we haven't inserted it
            if "id" not in channel_values.keys():
                id = self._insert_sub(
                    channel_id, channel_values["channel_title"], channel_values["latest_vid"], channel_values["active"]
                )
                # now add the returned ID from the insert to the dict so we know it's been added
                channel_values["id"] = int(id)
            elif "update_pending" in channel_values.keys() and channel_values["update_pending"]:
                # update both the latest vid as well as the active status
                self._update_latest_vid_for_channel_sub(channel_values["id"], channel_values["latest_vid"])
                self._update_sub_active_status(channel_values["id"], channel_values["active"])
                # set the update_pending flag to false
                channel_values["update_pending"] = False

    @check_for_new_videos.before_loop
    async def before_insert_or_update_subs_in_db(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(MarvinTube(bot))
