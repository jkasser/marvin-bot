import discord
import random
import json
import requests
import os
import asyncio
import yaml
from assets.data.quotes import *
from discord.ext import commands
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinStandup(commands.Cog):
    JOKES_BASE_DIR = './assets/data/'
    JOKES_FILES = {
        "wocka": "wocka.json",
        "stupid": "stupidstuff.json",
        "reddit": "reddit.json"
    }

    def __init__(self, bot):
        self.bot = bot
        self.jokes_list = {
            "wocka": self.load_wocka_jokes(),
            "reddit":  self.load_reddit_jokes(),
            "stupid": self.load_stupid_jokes()
        }


    def load_reddit_jokes(self):
        with open(self.JOKES_BASE_DIR + self.JOKES_FILES["reddit"]) as reddit_json:
            reddit_jokes = json.load(reddit_json)
            return reddit_jokes

    def load_stupid_jokes(self):
        with open(self.JOKES_BASE_DIR + self.JOKES_FILES["stupid"]) as stupid_json:
            stupid_jokes = json.load(stupid_json)
            return stupid_jokes

    def load_wocka_jokes(self):
        with open(self.JOKES_BASE_DIR + self.JOKES_FILES["wocka"]) as wocka_json:
            wocka_jokes = json.load(wocka_json)
            return wocka_jokes

    @commands.command(name='joke', help='Want to hear something funny?')
    async def tell_joke(self, ctx):
        joke_category = random.choice(list(self.jokes_list.keys()))
        joke_choice = random.choice(self.jokes_list[joke_category])
        if joke_category.lower() == 'reddit':
            await ctx.send(joke_choice["title"])
            await asyncio.sleep(1)
            await ctx.send(joke_choice["body"])
        else:
            # Wocka and Stupid json files have the same format
            await ctx.send(joke_choice["body"])


def setup(bot):
    bot.add_cog(MarvinStandup(bot))
