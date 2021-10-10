import yaml
import os
import requests
import discord
import datetime
from utils.helper import get_user_friendly_date_from_string, parse_num
from discord.ext import commands, tasks
import asyncio
import functools
from concurrent.futures.thread import ThreadPoolExecutor


class Covid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('config.yaml', 'r') as file:
            cfg = yaml.safe_load(file)
        env = os.environ.get('ENV', 'dev')
        self.us_politics_channel = cfg["disc"][env]["us_politics_channel"]
        self.base_url = "http://covidtracking.com/api/"
        self.headers = {
            'Content-Type': "application/json"
        }
        self.daily_covid_stats.start()

    def parse_covid_response(self, data: dict):
        # if province is in the dictionary, then we need to dig a bit deeper
        embed = discord.Embed(title="USA Covid Stats",
                              color=0x900C3F,
                              timestamp=datetime.datetime.now().astimezone())

        embed.add_field(name='Last Updated', value=f'**{get_user_friendly_date_from_string(data["lastModified"])}**',
                            inline=False)
        embed.add_field(name='Positive Tests', value=f'**{parse_num(data["positive"])}**',
                        inline=False)
        embed.add_field(name='Current Hospitalized', value=f'**{parse_num(data["hospitalizedCurrently"])}**', inline=False)
        embed.add_field(name='Current ICU', value=f'**{parse_num(data["inIcuCurrently"])}**', inline=False)
        embed.add_field(name='Current Ventilator', value=f'**{parse_num(data["onVentilatorCurrently"])}**', inline=False)
        embed.add_field(name='Recovered', value=f'**{parse_num(data["recovered"])}**', inline=False)
        embed.add_field(name='Deaths', value=f'**{parse_num(data["death"])}**', inline=False)

        embed.add_field(name='Death Increase', value=f'**{parse_num(data["deathIncrease"])}**', inline=False)
        embed.add_field(name='Hospitalized Increase', value=f'**{parse_num(data["hospitalizedIncrease"])}**', inline=False)
        embed.add_field(name='Positive Test Increase', value=f'**{parse_num(data["positiveIncrease"])}**', inline=False)
        return embed

    def get_covid_stats(self):
        endpoint = '/us'
        url = self.base_url + endpoint
        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            embed = self.parse_covid_response(r.json()[0])
            return embed

    @commands.command(name='getcovidstats', aliases=['covidcases', 'covidstats', 'getcovidcases', 'covid'],
                      help='Get the latest statistics on covid 19 for the USA (56 states and territories included)')
    async def get_latest_global(self, ctx):
        loop = asyncio.get_event_loop()
        embed = await loop.run_in_executor(ThreadPoolExecutor(), self.get_covid_stats)
        await ctx.send(embed=embed)

    @tasks.loop(hours=1)
    async def daily_covid_stats(self):
            now = datetime.datetime.now().astimezone()
            # we really only want to alert people on the day of (relative to them)
            if 0 <= now.hour < 1:
                loop = asyncio.get_event_loop()
                stats = await loop.run_in_executor(ThreadPoolExecutor(), self.get_covid_stats)
                us_politics = self.bot.get_channel(self.us_politics_channel)
                await us_politics.send(embed=stats)

    @daily_covid_stats.before_loop
    async def before_daily_covid_stats(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Covid(bot))
