import yaml
import requests
from datetime import datetime
from pytz import reference
import os
from utils.db import MarvinDB


class Riot(MarvinDB):

    ASSETS_BASE_DIR = '/assets/riot_games/'

    TABLE_NAME = 'riot_games'

    RIOT_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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

    CHECK_IF_EXISTS_BY_ID = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE summoner_id=? LIMIT 1)"""
    CHECK_IF_EXISTS_BY_NAME = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE summoner_name=? LIMIT 1)"""

    def __init__(self):
        super(Riot, self).__init__()
        # Create the database
        self.riot_table = self.create_table(self.conn, self.RIOT_TABLE)
        # Riot API Stuff
        file = open(os.path.dirname(os.path.dirname(__file__)) + '/config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        region = cfg["riot"]["region"]
        self.key = cfg["riot"]["key"]
        self.base_url = f'https://{region}.api.riotgames.com/lol/'

    def get_clash_schedule(self):
        endpoint = self.base_url + f'clash/v1/tournaments?api_key={self.key}'
        r = requests.get(endpoint)
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
        endpoint = self.base_url + f'summoner/v4/summoners/by-name/{summoner_name}?api_key={self.key}'
        r = requests.get(endpoint)
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

    def insert_summoner_into_db(self, values):
        """ Values: summoner_name,summoner_id,account_id,puuid,summoner_level,profile_icon,revision_date in a tuple """
        return self.insert_query(self.INSERT_SUMMONER, values)

    def get_summoner_by_name(self, summoner_name):
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_SUMMONER_BY_NAME, (summoner_name,)).fetchone()
        self.conn.commit()
        return results

    def check_if_summoner_exists_by_id(self, summoner_id):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS_BY_ID, (summoner_id,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def check_if_summoner_exists_by_name(self, summoner_name):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS_BY_NAME, (summoner_name,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def check_if_summoner_needs_update(self, summoner_id, current_revision_date):
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_SUMMONER_BY_ID, (summoner_id,)).fetchone()
        if results[7] < current_revision_date:
            return True
        else:
            return False

    def update_summoner(self, values):
        """summoner_level = ?, profile_icon = ?, revision_date = ? WHERE summoner_id = ?"""
        cur = self.conn.cursor()
        cur.execute(self.UPDATE_SUMMONER, values)
        self.conn.commit()

    def get_profile_img_for_id(self, profile_icon_id):
        profile_icon = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + self.ASSETS_BASE_DIR + f'10.20.1/img/profileicon/{str(profile_icon_id)}.png'
        return profile_icon
