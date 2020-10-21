import yaml
import requests
import os
import shutil
import tarfile
import urllib.request
import time
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pytz import reference
from utils.db import MarvinDB
from utils.helper import get_user_friendly_date_from_string, get_current_hour_of_day


class Riot(MarvinDB, commands.Cog):

    ASSETS_BASE_DIR = '/assets/riot_games/'

    TABLE_NAME = 'riot_games'
    SUMMONER_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        summoner_name text NOT NULL,
        summoner_id text not NULL,
        account_id text NOT NULL,
        puuid text NOT NULL,
        summoner_level integer NOT NULL,
        profile_icon integer NOT NULL,
        revision_date integer NOT NULL
    );"""
    INSERT_SUMMONER = f"""INSERT INTO {TABLE_NAME}(summoner_name,summoner_id,account_id,puuid,summoner_level,profile_icon,revision_date) VALUES(?,?,?,?,?,?,?)"""
    UPDATE_SUMMONER = f"""UPDATE {TABLE_NAME} SET summoner_level = ?, profile_icon = ?, revision_date = ? WHERE summoner_id = ?"""
    FIND_SUMMONER_BY_ID = f"""SELECT * FROM {TABLE_NAME} WHERE summoner_id = ?"""
    FIND_SUMMONER_BY_NAME = f"""SELECT * FROM {TABLE_NAME} WHERE summoner_name = ?"""
    CHECK_IF_SUMMONER_EXISTS_BY_ID = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE summoner_id=? LIMIT 1)"""
    CHECK_IF_SUMMONER_EXISTS_BY_NAME = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE summoner_name=? LIMIT 1)"""

    # Data dragon assets table
    ASSETS_TABLE_NAME = 'assets_ver'
    ASSETS_VER_TABLE =  f"""CREATE TABLE IF NOT EXISTS {ASSETS_TABLE_NAME} (
        id integer PRIMARY KEY,
        current_version text NOT NULL
    );
    """
    INSERT_LATEST_DATA_VERSION = F"""INSERT INTO {ASSETS_TABLE_NAME}(current_version) VALUES(?)"""
    UPDATE_LATEST_DATA_VERSION = F"""UPDATE {ASSETS_TABLE_NAME} SET current_version = ?"""
    CHECK_IF_CURRENT_VER_EXISTS = F"""SELECT EXISTS(SELECT * FROM {ASSETS_TABLE_NAME} LIMIT 1)"""
    GET_ASSETS_LATEST_VERSION = f"""SELECT current_version FROM {ASSETS_TABLE_NAME}"""

    # Issue tracker
    LOL_STATUS_TABLE_NAME = 'lol_status'
    LOL_STATUS_TABLE =  f"""CREATE TABLE IF NOT EXISTS {LOL_STATUS_TABLE_NAME} (
        id integer PRIMARY KEY,
        issue_hash text NOT NULL
    );
    """
    INSERT_ISSUE_HASH = F"""INSERT INTO {LOL_STATUS_TABLE_NAME} (issue_hash) VALUES(?)"""
    CHECK_ISSUE_HASH = f"""SELECT EXISTS(SELECT * FROM {LOL_STATUS_TABLE_NAME} WHERE issue_hash=? LIMIT 1)"""

    def __init__(self, bot):
        super(Riot, self).__init__()
        # setup bot for cogs
        self.bot = bot
        # Create the database
        self.summoner_table = self.create_table(self.conn, self.SUMMONER_TABLE)
        self.data_version_table = self.create_table(self.conn, self.ASSETS_VER_TABLE)
        self.issue_table = self.create_table(self.conn, self.LOL_STATUS_TABLE)
        # Riot API Stuff
        file = open(os.path.dirname(os.path.dirname(__file__)) + '/config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        region = cfg["riot"]["region"]
        self.key = cfg["riot"]["key"]
        self.base_url = f'https://{region}.api.riotgames.com/lol/'
        self.headers = {
            "Content-Type": "application/json",
            "X-Riot-Token": self.key
        }
        self.get_rito_status.start()
        self.check_and_update_latest_assets_version.start()

    def get_clash_schedule(self):
        endpoint = self.base_url + f'clash/v1/tournaments'
        r = requests.get(endpoint, headers=self.headers)
        if r.status_code == 200:
            schedule = [f'All timezones are in {reference.LocalTimezone().tzname(datetime.utcnow())}']
            for x in r.json():
                name = x["nameKey"].capitalize() + ' ' + ' '.join(x["nameKeySecondary"].split('_')).capitalize()
                registration = datetime.fromtimestamp(x["schedule"][0]["registrationTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                start_time = datetime.fromtimestamp(x["schedule"][0]["startTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                is_cancelled = x["schedule"][0]["cancelled"]
                if is_cancelled:
                    is_cancelled = 'Unfortunately, yes :('
                else:
                    is_cancelled = 'No'
                schedule.append(f'Tournament: {name}\nRegistration Date: {registration}\nStart Time: {start_time}\nHas it been cancelled? {is_cancelled}\n')
            response = '\n'.join(sorted(schedule))
        else:
            response = r.status_code, r.text
        return response

    def get_and_update_summoner_from_riot_by_name(self, summoner_name):
        endpoint = self.base_url + f'summoner/v4/summoners/by-name/{summoner_name}'
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
            if not self.check_if_summoner_exists_by_id(summoner_id):
                self.insert_summoner_into_db(
                    (summoner_name,summoner_id,account_id,puuid,summoner_level,profile_icon_id, revision_date)
                )
            else:
                self.update_summoner((summoner_level, profile_icon_id, revision_date, summoner_id))
            return summoner_name, summoner_level, profile_icon_id

    def insert_summoner_into_db(self, values: tuple):
        """ Values: summoner_name,summoner_id,account_id,puuid,summoner_level,profile_icon,revision_date in a tuple """
        return self.insert_query(self.INSERT_SUMMONER, values)

    def get_summoner_by_name(self, summoner_name: str):
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_SUMMONER_BY_NAME, (summoner_name,)).fetchone()
        self.conn.commit()
        return results

    def check_if_summoner_exists_by_id(self, summoner_id: id):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_SUMMONER_EXISTS_BY_ID, (summoner_id,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def check_if_summoner_exists_by_name(self, summoner_name: str):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_SUMMONER_EXISTS_BY_NAME, (summoner_name,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def check_if_summoner_needs_update(self, summoner_id: str, current_revision_date: int):
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_SUMMONER_BY_ID, (summoner_id,)).fetchone()
        if results[7] < current_revision_date:
            return True
        else:
            return False

    def update_summoner(self, values: tuple):
        """summoner_level = ?, profile_icon = ?, revision_date = ? WHERE summoner_id = ?"""
        cur = self.conn.cursor()
        cur.execute(self.UPDATE_SUMMONER, values)
        self.conn.commit()

    def get_profile_img_for_id(self, profile_icon_id: int):
        profile_icon = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + self.ASSETS_BASE_DIR + f'10.20.1/img/profileicon/{str(profile_icon_id)}.png'
        return profile_icon

    def get_latest_data_version(self):
        url = 'https://ddragon.leagueoflegends.com/realms/na.json'
        r = requests.get(url)
        if r.status_code == 200:
            current_version = r.json()["v"]
            cdn = r.json()["cdn"]
            assets_url = f'{cdn}/dragontail-{current_version}.tgz'
            return current_version, assets_url
        else:
            return

    def check_if_assets_current_version_exists(self):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_CURRENT_VER_EXISTS).fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def get_current_assets_version_from_db(self):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_ASSETS_LATEST_VERSION).fetchone()
        self.conn.commit()
        return results

    def insert_assets_current_version(self, current_version: str):
        """ Values: current_version"""
        return self.insert_query(self.INSERT_LATEST_DATA_VERSION, (current_version,))

    def update_assets_current_version(self, current_version: str):
        """current_version=?"""
        cur = self.conn.cursor()
        cur.execute(self.UPDATE_LATEST_DATA_VERSION, (current_version,))
        self.conn.commit()

    def download_new_assets(self, url, version_name):
        file_name = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + self.ASSETS_BASE_DIR + f'{version_name}.tgz'
        urllib.request.urlretrieve(url, file_name)
        return file_name

    def delete_existing_asset(self):
        try:
            path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + self.ASSETS_BASE_DIR
            for dir in os.listdir(path):
                if not dir.endswith('.tgz'):
                    os.chmod(path + dir, 0o0777)
                    if not os.path.isdir(path + dir):
                        # os.remove is for files
                        os.remove(path + dir)
                    else:
                        # recursively remove a dir and everything in it
                        shutil.rmtree(path + dir)
        except Exception as e:
            print(e)
            return

    def extract_assets(self, file_to_extract):
        tar = tarfile.open(file_to_extract, 'r:gz')
        tar.extractall(path=os.path.dirname(file_to_extract))
        tar.close()
        os.remove(file_to_extract)

    def get_and_parse_riot_status_issues(self):
        new_status_url = 'https://lol.secure.dyn.riotcdn.net/channels/public/x/status/na1.json'
        issues = []
        r = requests.get(new_status_url)
        if r.status_code == 200:
            if len(r.json()["incidents"]) > 0:
                for incident in r.json()["incidents"]:
                    issue = {}
                    issue["title"] = incident["titles"][0]["content"]
                    issue["severity"] = incident["incident_severity"]
                    issue["created"] = get_user_friendly_date_from_string(incident["created_at"])
                    if len(incident["updates"]) > 0:
                        issue["updates"] = incident["updates"][0]["translations"][0]["content"]
                    issue["hash"] = ''.join(issue["title"].split(' '))+''.join(issue["created"].replace(',', '').split(' '))
                    issues.append(issue)
        return issues

    def check_if_issue_hash_exists(self, hash_id: str):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_ISSUE_HASH, (hash_id,)).fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def insert_issue_hash(self, issue_hash: str):
        """ Values: issue_hash"""
        return self.insert_query(self.INSERT_ISSUE_HASH, (issue_hash,))

    def get_match_by_match_id(self, match_id):
        r = requests.get(self.base_url + 'match/v4/matches/' + str(match_id), headers=self.headers)
        return r.json()

    def get_match_timeline_by_match_id(self, match_id):
        r = requests.get(self.base_url + 'match/v4/timelines/by-match/' + str(match_id), headers=self.headers)
        return r.json()

    @commands.command(name='clash', help='Get current and upcoming clash tournament schedule.')
    async def get_clash(self, ctx):
        schedule = self.get_clash_schedule()
        await ctx.send(str(schedule))

    @commands.command(name='getsummoner', help='Pass in a summoner name and to get their info!')
    async def get_summoner(self, ctx, summoner_name):
        summoner_name = summoner_name.lower()
        results = self.get_summoner_by_name(summoner_name)
        if results is None:
            try:
                name, summoner_level, profile_icon_id = self.get_and_update_summoner_from_riot_by_name(summoner_name)
            # this will return None if no results are found which raises a type error
            except TypeError:
                await ctx.send(f'Summoner: {summoner_name} was not found! Make sure you have the spelling correct!')
                return
        else:
            one_day_ago = int(str(time.time()).replace('.', '')[:len(str(results[7]))]) - 86400
            if results[7] <= one_day_ago:
                # its been awhile, let's get new info
                name, summoner_level, profile_icon_id = self.get_and_update_summoner_from_riot_by_name(summoner_name)
            else:
                name, summoner_level, profile_icon_id = results[1], results[5], results[6]
        embedded_link = discord.Embed(title=name, description=summoner_level, color=0x8b0000)
        # Get the summoner icon
        disc_file = discord.File(self.get_profile_img_for_id(profile_icon_id), filename=f'{profile_icon_id}.png')
        embedded_link.set_image(url=f'attachment://{profile_icon_id}.png')
        await ctx.send(file=disc_file, embed=embedded_link)

    @commands.command(name='updatesummoner', help='Pass in a summoner name to update them in the databse')
    async def update_summoner(self, ctx, summoner_name):
        summoner_name = summoner_name.lower()
        try:
            name, summoner_level, profile_icon_id = self.get_and_update_summoner_from_riot_by_name(summoner_name)
        except TypeError:
            await ctx.send(f'Summoner: {summoner_name} was not found! Make sure you have the spelling correct!')
            return
        embedded_link = discord.Embed(title=name, description=summoner_level, color=0x8b0000)
        # Get the summoner icon
        disc_file = discord.File(self.get_profile_img_for_id(profile_icon_id), filename=f'{profile_icon_id}.png')
        embedded_link.set_image(url=f'attachment://{profile_icon_id}.png')
        await ctx.send(file=disc_file, embed=embedded_link)

    @tasks.loop(hours=2)
    async def check_and_update_latest_assets_version(self):
        hour = get_current_hour_of_day()
        if hour >= 23 or hour <= 5:
            api_updates_channel = self.bot.get_channel(763088226860138576)
            api_current_version, cdn = self.get_latest_data_version()
            try:
                if self.check_if_assets_current_version_exists():
                    assets_db_version = self.get_current_assets_version_from_db()[0]
                    # See if the api version is greater than our current one
                    if int(''.join(api_current_version.split('.'))) > int(''.join(assets_db_version.split('.'))):
                        await api_updates_channel.send(f'Our current version: {assets_db_version} is out of date!'
                                                       f'\nDownloading latest version: {api_current_version}')
                        # Update our local assets
                        new_assets = self.download_new_assets(cdn, api_current_version)
                        # Delete our local copy
                        self.delete_existing_asset()
                        # Extract the new one
                        await api_updates_channel.send('Extracting new assets!')
                        self.extract_assets(file_to_extract=new_assets)
                        # Now Update it in the DB
                        self.update_assets_current_version(current_version=api_current_version)
                        await api_updates_channel.send(f'We are now using LoL assets version: {api_current_version}')
                    # otherwise if they are equal then just say we are on the most current version
                    elif int(''.join(api_current_version.split('.'))) == int(''.join(assets_db_version.split('.'))):
                        # await api_updates_channel.send(f'We are on the most current LoL assets version: {assets_db_version}')
                        return
                else:
                    # If the field doesn't exist then download the latest version
                    # Update our local assets
                    new_assets = self.download_new_assets(cdn, api_current_version)
                    # Delete our local copy
                    self.delete_existing_asset()
                    # Extract the new one
                    self.extract_assets(file_to_extract=new_assets)
                    # Add it to the DB
                    self.insert_assets_current_version(api_current_version)
                    await api_updates_channel.send(f'We are now using LoL assets version: {api_current_version}')
            except Exception as e:
                await api_updates_channel.send(e)

    @tasks.loop(minutes=15)
    async def get_rito_status(self):
        status_channel = self.bot.get_channel(763153164798394378)
        issues = self.get_and_parse_riot_status_issues()
        if len(issues) > 0:
            for x in issues:
                if self.check_if_issue_hash_exists(x["hash"]):
                    continue
                else:
                    if x["severity"] == "info":
                        color = 0xf8d568
                    else:
                        color = 0xff0000
                    embedded_link = discord.Embed(title=x["title"], description=x["updates"], color=color)
                    embedded_link.add_field(name="created", value=x["created"])
                    await status_channel.send(embed=embedded_link)
                    self.insert_issue_hash(x["hash"])

    @check_and_update_latest_assets_version.before_loop
    async def before_check_and_update_latest_assets_version(self):
      await self.bot.wait_until_ready()

    @get_rito_status.before_loop
    async def before_get_rito_status(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Riot(bot))
