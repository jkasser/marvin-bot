import requests
import yaml
import discord
from discord.ext import commands, tasks
from sqlite3 import Error
from utils.db import MarvinDB
from utils.helper import get_user_friendly_date_from_string, get_slug_from_url
from datetime import timedelta, date


class Storage(commands.Cog):

    def __init__(self):
        super().__init__()
        file = open('../config.yaml', 'r')
        self.cfg = yaml.load(file, Loader=yaml.FullLoader)
        key = self.cfg["google"]["key"]
        project_identifier = self.cfg["google"]["project_id"]
        self.base_url = 'https://storage.googleapis.com/storage/v1/b/'
        self.url = f'{self.base_url}?project={project_identifier}&key={key}'
        self.bucket_location = 'US-WEST4' # las vegas
        # auth headers
        bearer = self.cfg["google"]["bearer"]
        self.headers = {
            "Authorization": f"Bearer {bearer}"
        }

    def create_bucket(self, name="marvinbot"):
        bucket_payload = {
            "name": name,
            "location": self.bucket_location,
            "storageClass": "STANDARD"
        }
        r = requests.post(self.url, json=bucket_payload, headers=self.headers)
        if r.status_code == 200:
            bucket_link = r.json()["selfLink"]
            return bucket_link
        else:
            return f'{r.status_code}: {r.json()["error"]["message"]}'

    def get_bucket(self):
        r = requests.get(self.url, headers=self.headers)
        if r.status_code == 200:
            return r.json()["items"]
        else:
            return f'{r.status_code}: {r.json()["error"]["message"]}'

    def delete_bucket(self, name="marvinbot"):
        r = requests.delete(self.base_url+name, headers=self.headers)
        if r.status_code == 204:
            return f'Bucket {name} deleted successfully!'
        else:
            return r.status_code, r.text

    def get_policy(self):


if __name__ == '__main__':
    r = Storage().get_bucket()
    print(r)