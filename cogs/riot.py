import yaml
import requests
import os
import shutil
import tarfile
import urllib.request
import time
import discord
import re
from discord.ext import commands, tasks
from datetime import datetime
from pytz import reference
from utils.db import MarvinDB
from utils.message_handler import MessageHandler
from utils.helper import get_user_friendly_date_from_string, get_current_hour_of_day
import asyncio
from concurrent.futures.thread import ThreadPoolExecutor


class Riot(MarvinDB, commands.Cog):

    ASSETS_BASE_DIR = "/assets/riot_games/"

    TABLE_NAME = "riot_games"

    # Fields
    SUMMONER_NAME = "summoner_name"
    SUMMONER_ID = "summoner_id"
    ACCOUNT_ID = "account_id"
    PUUID = "puuid"
    SUMMONER_LEVEL = "summoner_level"
    PROFILE_ICON = "profile_icon"
    REVISION_DATE = "revision_date"

    # Data dragon assets table
    ASSETS_TABLE_NAME = "assets_ver"
    CURRENT_VERSION = "current_version"
    # Issue tracker
    LOL_STATUS_TABLE_NAME = "lol_status"
    ISSUE_HASH = "issue_hash"

    def __init__(self, bot):
        super(Riot, self).__init__()
        # setup bot for cogs
        self.bot = bot
        # Create the database
        self.summoner_table = self.select_collection(self.TABLE_NAME)
        self.data_version_table = self.select_collection(self.ASSETS_TABLE_NAME)
        self.issue_table = self.select_collection(self.LOL_STATUS_TABLE_NAME)

        # Riot API Stuff
        env = os.environ.get("ENV", "dev")
        self.api_updates_channel = self.lol_channel = self.bot.config["disc"][env][
            "api_updates_channel"
        ]
        self.status_channel = self.lol_channel = self.bot.config["disc"][env]["status_channel"]
        region = self.bot.config["riot"]["region"]
        self.key = self.bot.config["riot"]["key"]
        self.base_url = f"https://{region}.api.riotgames.com/lol/"
        self.headers = {"Content-Type": "application/json", "X-Riot-Token": self.key}
        self.assets_version = None
        self.get_rito_status.start()
        self.check_and_update_latest_assets_version.start()

    def _get_clash_schedule(self):
        endpoint = self.base_url + f"clash/v1/tournaments"
        r = requests.get(endpoint, headers=self.headers)
        if r.status_code == 200:
            schedule = [
                f"All timezones are in {reference.LocalTimezone().tzname(datetime.utcnow())}"
            ]
            for x in r.json():
                name = (
                    " ".join(x["nameKey"].split("_")).capitalize()
                    + " "
                    + " ".join(x["nameKeySecondary"].split("_")).capitalize()
                )
                registration = datetime.fromtimestamp(
                    x["schedule"][0]["registrationTime"] / 1000
                ).strftime("%Y-%m-%d %H:%M:%S")
                start_time = datetime.fromtimestamp(
                    x["schedule"][0]["startTime"] / 1000
                ).strftime("%Y-%m-%d %H:%M:%S")
                is_cancelled = x["schedule"][0]["cancelled"]
                if is_cancelled:
                    is_cancelled = "Unfortunately, yes :("
                else:
                    is_cancelled = "No"
                schedule.append(
                    f"Tournament: {name}\nRegistration Date: {registration}\nStart Time: {start_time}"
                    f"\nHas it been cancelled? {is_cancelled}\n"
                )
            response = "\n".join(sorted(schedule))
        else:
            response = r.status_code, r.text
        return response

    def _get_and_update_summoner_from_riot_by_name(self, summoner_name):
        endpoint = self.base_url + f"summoner/v4/summoners/by-name/{summoner_name}"
        r = requests.get(endpoint, headers=self.headers)
        if r.status_code == 200:
            summoner_body = r.json()
            summoner_name = summoner_body["name"]
            summoner_id = summoner_body["id"]
            puuid = summoner_body["puuid"]
            account_id = summoner_body["accountId"]
            profile_icon_id = summoner_body["profileIconId"]
            summoner_level = summoner_body["summonerLevel"]
            revision_date = summoner_body["revisionDate"]
            if not self._check_if_summoner_exists_by_id(summoner_id):
                self._insert_summoner_into_db(
                    name=summoner_name,
                    summoner_id=summoner_id,
                    account_id=account_id,
                    puuid=puuid,
                    summoner_level=summoner_level,
                    profile_icon=profile_icon_id,
                    revision_date=revision_date,
                )
            else:
                self._update_summoner_in_db(
                    summoner_id,
                    {
                        self.SUMMONER_NAME: summoner_name,
                        self.SUMMONER_LEVEL: summoner_level,
                        self.PROFILE_ICON: profile_icon_id,
                        self.REVISION_DATE: revision_date,
                    }
                )
            return summoner_name, summoner_level, profile_icon_id

    def _insert_summoner_into_db(self, name, summoner_id, account_id, puuid, summoner_level, profile_icon, revision_date):
        return self.summoner_table.insert_one(
            {
                self.SUMMONER_NAME: name,
                self.SUMMONER_ID: summoner_id,
                self.ACCOUNT_ID: account_id,
                self.PUUID: puuid,
                self.SUMMONER_LEVEL: summoner_level,
                self.PROFILE_ICON: profile_icon,
                self.REVISION_DATE: revision_date,
            }
        )

    def _get_summoner_by_name(self, summoner_name):
        results = self.run_find_one_query(
            table=self.summoner_table,
            query_to_run={
                self.SUMMONER_NAME: str(summoner_name),
            }
        )
        return results

    def _check_if_summoner_exists_by_id(self, summoner_id):
        results = self.run_find_one_query(
            table=self.summoner_table,
            query_to_run={
                self.SUMMONER_ID: summoner_id
            }
        )
        if results:
            return True
        else:
            return False

    def _check_if_summoner_exists_by_name(self, summoner_name: str):
        results = self.run_find_one_query(
            table=self.summoner_table,
            query_to_run={
                self.SUMMONER_NAME: summoner_name
            }
        )
        if results:
            return True
        else:
            return False

    def _check_if_summoner_needs_update(
        self, summoner_id: str, current_revision_date: int
    ):
        results = self.run_find_one_query(
            table=self.summoner_table,
            query_to_run={
                self.SUMMONER_ID: summoner_id
            }
        )
        if results[self.REVISION_DATE] < current_revision_date:
            return True
        else:
            return False

    def _update_summoner_in_db(self, summoner_id, values_to_set: dict):
        """summoner_level = ?, profile_icon = ?, revision_date = ? WHERE summoner_id = ?"""
        self.summoner_table.update_one(
            {
                self.SUMMONER_ID: summoner_id,
            },
            {
                "$set": values_to_set
            }
        )

    def _get_profile_img_for_id(self, profile_icon_id: int):
        parent_path = (
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            + self.ASSETS_BASE_DIR
        )
        # walk the directory and find the assets directory for the current patch based on what is already downloaded
        for asset_dir in os.listdir(parent_path):
            if self._find_assets_dir_by_regex(asset_dir):
                self.assets_version = asset_dir
                break
        # otherwise just use whatever we have declared
        profile_icon = (
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            + self.ASSETS_BASE_DIR
            + f"{self.assets_version}/img/profileicon/{str(profile_icon_id)}.png"
        )
        return profile_icon

    def _get_latest_data_version(self):
        url = "https://ddragon.leagueoflegends.com/realms/na.json"
        r = requests.get(url)
        if r.status_code == 200:
            current_version = r.json()["v"]
            cdn = r.json()["cdn"]
            assets_url = f"{cdn}/dragontail-{current_version}.tgz"
            return current_version, assets_url
        else:
            return

    def _find_assets_dir_by_regex(self, file_name):
        expr = re.compile("^\d{0,2}\.\d{0,2}\.\d{0,2}$")
        try:
            if expr.search(file_name).group() is not None:
                return True
        except AttributeError:
            return False

    def _check_if_assets_current_version_exists(self):
        results = self.run_find_one_query(
            table=self.data_version_table,
            query_to_run={}
        )
        if results is not None:
            return True
        else:
            return False

    def _get_current_assets_version_from_db(self):
        results = self.run_find_one_query(
            table=self.data_version_table,
            query_to_run={}
        )
        return results

    def _insert_assets_current_version(self, current_version: str):
        return self.data_version_table.insert_one(
            {
                self.CURRENT_VERSION: current_version
            }
        )

    def _update_assets_current_version(self, current_version: str):
        version = self.run_find_one_query(
            table=self.data_version_table,
            query_to_run={}
        )["_id"]
        return self.set_field_for_object_in_table(
            table=self.data_version_table,
            record_id_to_update=version,
            query_to_run={
                self.CURRENT_VERSION: current_version
            }
        )

    def _download_new_assets(self, url, version_name):
        path = (
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            + self.ASSETS_BASE_DIR
        )
        if not os.path.exists(path):
            os.mkdir(path)
        file_name = path + f"{version_name}.tgz"
        urllib.request.urlretrieve(url, file_name)
        return file_name

    def _delete_existing_asset(self):
        try:
            path = (
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                + self.ASSETS_BASE_DIR
            )
            for asset_dir in os.listdir(path):
                if not asset_dir.endswith(".tgz"):
                    os.chmod(path + asset_dir, 0o0777)
                    if not os.path.isdir(path + asset_dir):
                        # os.remove is for files
                        os.remove(path + asset_dir)
                    else:
                        # recursively remove a dir and everything in it
                        shutil.rmtree(path + asset_dir)
        except Exception as e:
            print(e)
            return

    def _extract_assets(self, file_to_extract):
        tar = tarfile.open(file_to_extract, "r:gz")
        tar.extractall(path=os.path.dirname(file_to_extract))
        tar.close()
        os.remove(file_to_extract)

    def get_and_parse_riot_status_issues(self):
        new_status_url = (
            "https://lol.secure.dyn.riotcdn.net/channels/public/x/status/na1.json"
        )
        issues = []
        r = requests.get(new_status_url)
        if r.status_code == 200:
            if len(r.json()["incidents"]) > 0:
                for incident in r.json()["incidents"]:
                    issue = {}
                    issue["title"] = incident["titles"][0]["content"]
                    issue["severity"] = incident["incident_severity"]
                    issue["created"] = get_user_friendly_date_from_string(
                        incident["created_at"]
                    )
                    if len(incident["updates"]) > 0:
                        issue["updates"] = incident["updates"][0]["translations"][0][
                            "content"
                        ]
                    issue["hash"] = "".join(issue["title"].split(" ")) + "".join(
                        issue["created"].replace(",", "").split(" ")
                    )
                    issues.append(issue)
        return issues

    def _check_if_issue_hash_exists(self, hash_id: str):
        results = self.run_find_one_query(
            table=self.data_version_table,
            query_to_run={
                self.ISSUE_HASH: hash_id
            }
        )
        if results is not None:
            return False
        else:
            return True

    def _insert_issue_hash(self, issue_hash: str):
        """Values: issue_hash"""
        return self.issue_table.insert_one(
            {
                self.ISSUE_HASH: issue_hash
            }
        )

    def _get_match_by_match_id(self, match_id):
        r = requests.get(
            self.base_url + "match/v4/matches/" + str(match_id), headers=self.headers
        )
        return r.json()

    def _get_match_timeline_by_match_id(self, match_id):
        r = requests.get(
            self.base_url + "match/v4/timelines/by-match/" + str(match_id),
            headers=self.headers,
        )
        return r.json()

    @commands.command(
        name="clash", help="Get current and upcoming clash tournament schedule."
    )
    async def get_clash(self, ctx):
        schedule = self._get_clash_schedule()
        for _ in MessageHandler(schedule).response:
            await ctx.send(str(_))

    @commands.command(
        name="getsummoner", help="Pass in a summoner name and to get their info!"
    )
    async def get_summoner(self, ctx, summoner_name):
        summoner_name = summoner_name.lower()
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            ThreadPoolExecutor(), self._get_summoner_by_name, summoner_name
        )
        if results is None:
            try:
                name, summoner_level, profile_icon_id = await loop.run_in_executor(
                    ThreadPoolExecutor(),
                    self._get_and_update_summoner_from_riot_by_name,
                    summoner_name,
                )
            # this will return None if no results are found which raises a type error
            except TypeError:
                await ctx.send(
                    f"Summoner: {summoner_name} was not found! Make sure you have the spelling correct!"
                )
                return
        else:
            one_day_ago = (
                int(str(time.time()).replace(".", "")[: len(str(results[self.REVISION_DATE]))]) - 86400
            )
            if results[self.REVISION_DATE] <= one_day_ago:
                # its been awhile, let's get new info
                name, summoner_level, profile_icon_id = await loop.run_in_executor(
                    ThreadPoolExecutor(),
                    self._get_and_update_summoner_from_riot_by_name,
                    summoner_name,
                )
            else:
                name, summoner_level, profile_icon_id = (
                    results[self.SUMMONER_NAME],
                    results[self.SUMMONER_LEVEL],
                    results[self.PROFILE_ICON],
                )
        embedded_link = discord.Embed(
            title=name, description=summoner_level, color=0x8B0000
        )
        # Get the summoner icon
        disc_file = discord.File(
            self._get_profile_img_for_id(profile_icon_id),
            filename=f"{profile_icon_id}.png",
        )
        embedded_link.set_image(url=f"attachment://{profile_icon_id}.png")
        await ctx.send(file=disc_file, embed=embedded_link)

    @commands.command(
        name="updatesummoner",
        help="Pass in a summoner name to update them in the databse",
    )
    async def update_summoner(self, ctx, summoner_name):
        summoner_name = summoner_name.lower()
        loop = asyncio.get_event_loop()
        try:
            name, summoner_level, profile_icon_id = await loop.run_in_executor(
                ThreadPoolExecutor(),
                self._get_and_update_summoner_from_riot_by_name,
                summoner_name,
            )
        except TypeError:
            await ctx.send(
                f"Summoner: {summoner_name} was not found! Make sure you have the spelling correct!"
            )
            return
        embedded_link = discord.Embed(
            title=name, description=summoner_level, color=0x8B0000
        )
        # Get the summoner icon
        disc_file = discord.File(
            self._get_profile_img_for_id(profile_icon_id),
            filename=f"{profile_icon_id}.png",
        )
        embedded_link.set_image(url=f"attachment://{profile_icon_id}.png")
        await ctx.send(file=disc_file, embed=embedded_link)

    @tasks.loop(hours=2)
    async def check_and_update_latest_assets_version(self):
        hour = get_current_hour_of_day()
        loop = asyncio.get_event_loop()
        if hour >= 23 or hour <= 11:
            api_updates_channel = self.bot.get_channel(self.api_updates_channel)
            api_current_version, cdn = await loop.run_in_executor(
                ThreadPoolExecutor(), self._get_latest_data_version
            )
            try:
                if self._check_if_assets_current_version_exists():
                    assets_db_version = self._get_current_assets_version_from_db()[self.CURRENT_VERSION]
                    # See if the api version is greater than our current one
                    if api_current_version > assets_db_version:
                        await api_updates_channel.send(
                            f"Our current version: {assets_db_version} is out of date!"
                            f"\nDownloading latest version: {api_current_version}"
                        )
                        # Update our local assets
                        new_assets = await loop.run_in_executor(
                            ThreadPoolExecutor(),
                            self._download_new_assets,
                            cdn,
                            api_current_version,
                        )
                        # Delete our local copy
                        self._delete_existing_asset()
                        # Extract the new one
                        self._extract_assets(file_to_extract=new_assets)
                        # Now Update it in the DB
                        self._update_assets_current_version(
                            current_version=api_current_version
                        )
                        await api_updates_channel.send(
                            f"We are now using LoL assets version: {api_current_version}"
                        )
                    # otherwise if they are equal then just say we are on the most current version
                    elif api_current_version == assets_db_version:
                        # this gets spammy as it prints every time the loop does, comment it out
                        # await api_updates_channel.send(f'We are on the most current LoL assets version:
                        # {assets_db_version}')
                        return
                else:
                    # If the field doesn't exist then download the latest version
                    # Update our local assets
                    new_assets = await loop.run_in_executor(
                        ThreadPoolExecutor(),
                        self._download_new_assets,
                        cdn,
                        api_current_version,
                    )
                    # Delete our local copy
                    self._delete_existing_asset()
                    # Extract the new one
                    self._extract_assets(file_to_extract=new_assets)
                    # Add it to the DB
                    self._insert_assets_current_version(api_current_version)
                    await api_updates_channel.send(
                        f"We are now using LoL assets version: {api_current_version}"
                    )
                self.assets_version = api_current_version
            except Exception as e:
                await api_updates_channel.send(e)
        else:
            if self._check_if_assets_current_version_exists():
                assets_db_version = self._get_current_assets_version_from_db()[self.CURRENT_VERSION]
                self.assets_version = assets_db_version

    @tasks.loop(minutes=15)
    async def get_rito_status(self):
        status_channel = self.bot.get_channel(self.status_channel)
        loop = asyncio.get_event_loop()
        issues = await loop.run_in_executor(
            ThreadPoolExecutor(), self.get_and_parse_riot_status_issues
        )
        if len(issues) > 0:
            for x in issues:
                if self._check_if_issue_hash_exists(x["hash"]):
                    continue
                else:
                    if x["severity"] == "info":
                        color = 0xF8D568
                    else:
                        color = 0xFF0000
                    embedded_link = discord.Embed(
                        title=x["title"], description=x["updates"], color=color
                    )
                    embedded_link.add_field(name="created", value=x["created"])
                    await status_channel.send(embed=embedded_link)
                    self._insert_issue_hash(x["hash"])

    @check_and_update_latest_assets_version.before_loop
    async def before_check_and_update_latest_assets_version(self):
        await self.bot.wait_until_ready()

    @get_rito_status.before_loop
    async def before_get_rito_status(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Riot(bot))
