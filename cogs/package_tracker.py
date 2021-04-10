import discord
import requests
import yaml
from discord.ext import commands
import asyncio
from concurrent.futures.thread import ThreadPoolExecutor


class PackageTracker(commands.Cog):

    def __init__(self):
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        self.username = cfg["usps"]["un"]
        self.password = cfg["usps"]["pw"]
        base_url = 'https://secure.shippingapis.com/ShippingAPI.dll?API=TrackV2'