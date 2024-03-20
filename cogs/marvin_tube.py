import requests
import os
import yaml
import asyncio
import functools
from discord.ext import commands, tasks
from utils.db import MarvinDB
from sqlite3 import Error
from asyncio import TimeoutError
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinTube(commands.Cog, MarvinDB):

    TABLE_NAME = "video_subs"

    # field names
    CHANNEL_ID = "channel_id"
    CHANNEL_TITLE = "channel_title"
    LATEST_VID = "latest_vid"
    ACTIVE = "active"

    def __init__(self, bot):
        super(MarvinTube, self).__init__()
        self.bot = bot
        # try to create the table
        try:
            self.video_subs = self.select_collection(self.TABLE_NAME)
        except Error as e:
            print(e)
        env = os.environ.get("ENV", "NOT SET")
        with open("config.yaml", "r") as file:
            cfg = yaml.safe_load(file)
        self.google_api_key = cfg["google"]["api_key"]
        self.base_url = "https://www.googleapis.com/youtube/v3/"
        self.channels_endpoint = "channels"
        self.headers = {"Accept": "application/json"}
        self.tv_channel_id = cfg["disc"][env]["video_channel"]
        # get the tables from the db
        subs = self._get_current_subs()
        self.channels = {}
        for sub in subs:
            self.channels[sub[self.CHANNEL_ID]] = dict(
                _id=sub["_id"],
                channel_title=sub[self.CHANNEL_TITLE],
                latest_vid=sub[self.LATEST_VID],
                active=sub[self.ACTIVE]
            )
        # start the loop to post videos
        self.check_for_new_videos.start()
        self.insert_or_update_subs_in_db.start()

    def _get_latest_video_for_channel_id(self, channel_id):
        latest_vid = {}
        r = requests.get(
            self.base_url
            + f"search?key={self.google_api_key}&channelId={channel_id}&order=date&maxResults=1&part=snippet"
        )
        if r.status_code == 200:
            # all the returned videos will be stored in the items list of dicts
            for video in r.json()["items"]:
                try:
                    latest_vid["channel_title"] = video["snippet"]["channelTitle"]
                    latest_vid["video_id"] = video["id"]["videoId"]
                    latest_vid["title"] = video["snippet"]["title"]
                except KeyError:
                    pass
            return latest_vid
        else:
            response = f'There was an error returning this request: {r.status_code}\n{r.json()["error"]["message"]}'
            return response

    def _get_channel_by_custom_name(self, channel_name):
        possible_channels = []
        # someone could have searched by a custom URL, so try to get fancy and let us search by the name
        r = requests.get(
            self.base_url
            + f"search?key={self.google_api_key}&order=relevance&maxResults=3&part=snippet,id&type=channel"
            f"&q={channel_name}"
        )
        if r.status_code == 200:
            for channel in r.json()["items"]:
                possible_channels.append(
                    {
                        "channel_id": channel["snippet"]["channelId"],
                        "channel_title": channel["snippet"]["channelTitle"],
                    }
                )
            return possible_channels
        else:
            response = (
                f"There was an error returning this request: {r.status_code}\n{r.text}"
            )
            return response

    # DB methods here
    def _get_current_subs(self):
        results = self.run_find_many_query(self.video_subs, {})
        if not results:
            results = []
        return results

    def _insert_sub(
        self, channel_id: str, channel_title: str, latest_vid: str, active: int
    ):
        """ Returns ID of inserted record. """
        # first see if the sub already exists
        sub = self.run_find_one_query(
            table=self.video_subs,
            query_to_run={
                self.CHANNEL_ID: channel_id
            }
        )
        if not sub:
            return self.video_subs.insert_one(
                {
                    self.CHANNEL_ID: channel_id,
                    self.CHANNEL_TITLE: channel_title,
                    self.LATEST_VID: latest_vid,
                    self.ACTIVE: active,
                }
            ).inserted_id
        else:
            return sub["_id"]

    def _update_latest_vid_for_channel_sub(self, sub_id, latest_vid: str):
        result = self.set_field_for_object_in_table(
            table=self.video_subs,
            record_id_to_update=sub_id,
            query_to_run={
                self.LATEST_VID: latest_vid,
            },
        )
        return result

    def _update_sub_active_status(self, sub_id, active: int):
        result = self.set_field_for_object_in_table(
            table=self.video_subs,
            record_id_to_update=sub_id,
            query_to_run={
                self.ACTIVE: active,
            }
        )
        return result

    @commands.command(
        name="getchannelsubs",
        help="Get a list of what youtube channels you are currently subscribed to!",
    )
    async def get_channel_subs(self, ctx):
        new_line = "\n"
        list_of_current_channels = []
        for channel, values in self.channels.items():
            if "_id" in values.keys():
                list_of_current_channels.append(
                    f'{values["_id"]} - {values[self.CHANNEL_TITLE]} - {self._get_active_status_from_bool(values[self.ACTIVE])}'
                )
            else:
                list_of_current_channels.append(
                    f'(ID NOT READY YET) - {values[self.CHANNEL_TITLE]} - {self._get_active_status_from_bool(values[self.ACTIVE])}'
                )
        await ctx.send(
            f"You are currently subscribed to: {new_line.join(list_of_current_channels)}"
        )

    @staticmethod
    def _get_active_status_from_bool(active: int):
        active_status = {
            1: "Active",
            0: "Inactive",
        }
        return active_status[active]

    @commands.command(
        name="updatechannelsub",
        help="Sets the provided channel ID to active/inactive depending on it's current status.",
    )
    async def update_channel_sub(self, ctx, sub_id=None):
        if sub_id is None:
            await ctx.send(
                "Which channel hash (the string I return when you call !getchannelsubs) would you like to update?"
            )

            def check(m):
                return m.author.name == ctx.author.name

            try:
                user_answer = await self.bot.wait_for(
                    "message", check=check, timeout=60
                )
                sub_id = user_answer.content
            except TimeoutError:
                await ctx.send("You took too long to respond! Good bye.")

        try:
            updated_any_value = False
            for channel, values in self.channels.items():
                if sub_id == values["_id"]:
                    if values[self.ACTIVE] == 0:
                        values[self.ACTIVE] = 1
                    else:
                        values[self.ACTIVE] = 0
                    updated_any_value = True
                    values["update_pending"] = True
                    await ctx.send(
                        f"I have updated your subscription to be {self._get_active_status_from_bool(values[self.ACTIVE])}!"
                    )
                    return
            if not updated_any_value:
                await ctx.send(
                    "I was unable to find a subscription to update! Please try again."
                )
                return
        except ValueError:
            await ctx.send(
                "Sorry. I was unable to parse the provided channel ID. Make sure it is just a number, e.g. 1"
            )

    @commands.command(
        name="subchannel",
        help="Subscribe to a youtube channel and have their latest videos posted"
        "to our tv channel!",
    )
    async def sub_channel(self, ctx, channel_id=None):
        timeout = 60

        def check(m):
            return m.author.name == ctx.author.name

        if channel_id is None:
            await ctx.send(
                "You haven't provided me with a channel ID or Channel Name. "
                "Could you grab that for me now?"
            )
            try:
                user_answer = await self.bot.wait_for(
                    "message", check=check, timeout=timeout
                )
                user_answer = user_answer.content
                if user_answer is not None:
                    await ctx.send(
                        f"Thanks! I will now try to subscribe to: {user_answer}"
                    )
                    channel_id = user_answer
            except TimeoutError:
                await ctx.send("You have taken too long to decide! Good-bye!")
                return
        # figure out if it's a channel ID or channel name
        loop = asyncio.get_event_loop()
        if not channel_id.lower().startswith("uc"):
            await ctx.send(
                "This looks like a channel name instead of a channel ID, is this correct? (yes/no)"
            )
            try:
                is_channel_id_answer = await self.bot.wait_for(
                    "message", check=check, timeout=timeout
                )
                is_channel_id_answer = is_channel_id_answer.content
                if is_channel_id_answer.lower() not in [
                    "yes",
                    "y",
                    "yep",
                    "yse",
                    "yess",
                ]:
                    channel_id = channel_id
                else:
                    # perform the channel name lookup
                    response = await loop.run_in_executor(
                        ThreadPoolExecutor(),
                        self._get_channel_by_custom_name,
                        channel_id,
                    )
                    if isinstance(response, list):
                        if len(response) == 0:
                            await ctx.send(
                                f"I found no matches based on the channel name of: {channel_id}. Please"
                                f" try again! Good bye."
                            )
                            return
                        elif len(response) == 1:
                            await ctx.send(
                                f"I have found one match! I will now subscribe you to "
                                f'{response[0]["channel_title"]}'
                            )
                            # set the channel_id here which should set it for the latest video check later
                            channel_id = response[0]["channel_id"]
                        else:
                            # if we have more than one result let's let the user choose them here
                            await ctx.send(
                                f"Your search has {len(response)} results! Which channel would you like "
                                f"to subscribe? You can make a note of the other channel ID if you were"
                                f" trying to subscribe more than 1! Please post the number of the channel "
                                f"that best matches what you want, or say cancel!"
                            )
                            strings = []
                            for idx, possible_channel in enumerate(response):
                                strings.append(
                                    f'{idx}. Title: {possible_channel["channel_title"]} - '
                                    f'ID: {possible_channel["channel_id"]}'
                                )
                            await ctx.send("\n".join(strings))
                            channel_selection = await self.bot.wait_for(
                                "message", check=check, timeout=timeout
                            )
                            channel_selection = channel_selection.content
                            if "cancel" in channel_selection.lower():
                                await ctx.send("Ok, goodbye!")
                            else:
                                try:
                                    choice = int(
                                        channel_selection.strip(" .!,:'-\"][{}@#$%")
                                    )
                                    channel_id = response[choice-1][self.CHANNEL_ID]
                                except ValueError:
                                    await ctx.send(
                                        "I was unable to parse your response. However, you can just call"
                                        " this command again and provide the channel ID of the channel "
                                        "you wish to subscribe to."
                                    )
                                    return

            except TimeoutError:
                await ctx.send("You have taken too long to decide! Good-bye!")
                return

        if channel_id not in self.channels.keys():
            disc_channel = self.bot.get_channel(int(self.tv_channel_id))
            # this is the first time we are retrieving this so let's do the whole shebang
            response = await loop.run_in_executor(
                ThreadPoolExecutor(), self._get_latest_video_for_channel_id, channel_id
            )
            if isinstance(response, dict):
                self.channels[channel_id] = {
                    self.ACTIVE: 1,
                    self.LATEST_VID: response["video_id"],
                    self.CHANNEL_TITLE: response["channel_title"],
                }
                # let's try to grab the channel name at this point
                await ctx.send(
                    f'Got it! We are now subscribed to "{response["channel_title"]}".\nPosting their latest'
                    f" video now!"
                )
                await disc_channel.send(
                    f'https://youtube.com/watch?v={response["video_id"]}'
                )
                return
            else:
                # if its not a dict we got a string back which means the API call failed, post the error to the channel
                await ctx.send(response)
                return
        else:
            await ctx.send(
                f'You are already subbed to {self.channels[channel_id]["channel_title"]}'
            )

    @tasks.loop(hours=4)
    async def check_for_new_videos(self):
        disc_channel = self.bot.get_channel(int(self.tv_channel_id))
        loop = asyncio.get_event_loop()
        for channel_id, channel_values in self.channels.items():
            # only grab active channel subscriptions
            if channel_values["active"]:
                # check channel k here, see if latest v == the latest channel
                response = await loop.run_in_executor(
                    ThreadPoolExecutor(),
                    self._get_latest_video_for_channel_id,
                    channel_id,
                )
                if isinstance(response, dict):
                    latest_video = response["video_id"]
                    if (
                        "latest_vid" in channel_values.keys()
                        and channel_values["latest_vid"] == latest_video
                    ):
                        continue
                    else:
                        # update the latest video id we have and post it to the channel
                        channel_values["latest_vid"] = latest_video
                        await disc_channel.send(
                            f"https://youtube.com/watch?v={latest_video}"
                        )
                        # set an update flag on the record in the dictionary so we know to update the DB
                        channel_values["update_pending"] = True
                else:
                    # if its not a dict we got a string back which means the API call failed,
                    # post the error to the channel
                    await disc_channel.send(response)
                    await disc_channel.send(
                        f'Setting the subscription for "{channel_values["channel_title"]}" to '
                        f"inactive"
                    )
                    # set the channel to inactive
                    channel_values["active"] = 0
                    # set an update flag on the record in the dictionary so we know to update the DB
                    channel_values["update_pending"] = True

    @check_for_new_videos.before_loop
    async def before_check_for_new_videos(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def insert_or_update_subs_in_db(self):
        loop = asyncio.get_event_loop()
        for channel_id, channel_values in self.channels.items():
            # if the ID isnt in the keys then we haven't inserted it
            if "_id" not in channel_values.keys():
                keyword_blocking_function = functools.partial(
                    self._insert_sub,
                    channel_id=channel_id,
                    channel_title=channel_values[self.CHANNEL_TITLE],
                    latest_vid=channel_values[self.LATEST_VID],
                    active=channel_values[self.ACTIVE],
                )
                channel_values["_id"] = await loop.run_in_executor(
                    ThreadPoolExecutor(), keyword_blocking_function
                )
            elif (
                "update_pending" in channel_values.keys()
                and channel_values["update_pending"] == True
            ):
                # update both the latest vid as well as the active status
                update_latest_vid_func = functools.partial(
                    self._update_latest_vid_for_channel_sub,
                    sub_id=channel_values["_id"],
                    latest_vid=channel_values[self.LATEST_VID],
                )
                await loop.run_in_executor(ThreadPoolExecutor(), update_latest_vid_func)

                update_active_status_func = functools.partial(
                    self._update_sub_active_status,
                    sub_id=channel_values["_id"],
                    active=channel_values[self.ACTIVE],
                )
                await loop.run_in_executor(
                    ThreadPoolExecutor(), update_active_status_func
                )
                # set the update_pending flag to false
                channel_values["update_pending"] = False

    @check_for_new_videos.before_loop
    async def before_insert_or_update_subs_in_db(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(MarvinTube(bot))
