import random
import json
import asyncio
from discord.ext import commands


class MarvinStandup(commands.Cog):
    JOKES_BASE_DIR = "./assets/data/"
    JOKES_FILES = {
        "wocka": "wocka.json",
        "stupid": "stupidstuff.json",
        "reddit": "reddit.json",
    }

    def __init__(self, bot):
        self.bot = bot
        self.jokes_list = {}
        for name, file in self.JOKES_FILES.items():
            self.jokes_list[name] = self.load_jokes_from_file(file)

    def load_jokes_from_file(self, file):
        with open(self.JOKES_BASE_DIR + file) as jokes_file:
            return json.load(jokes_file)

    @commands.command(name="joke", help="Want to hear something funny?")
    async def tell_joke(self, ctx):
        joke_category = random.choice(list(self.jokes_list.keys()))
        joke_choice = random.choice(self.jokes_list[joke_category])
        if joke_category.lower() == "reddit":
            await ctx.send(joke_choice["title"])
            await asyncio.sleep(1)
            await ctx.send(joke_choice["body"])
        else:
            # Wocka and Stupid json files have the same format
            await ctx.send(joke_choice["body"])


def setup(bot):
    bot.add_cog(MarvinStandup(bot))
