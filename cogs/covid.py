import yaml
import requests
import discord
import datetime
from utils.helper import get_user_friendly_date_from_string, parse_num
from discord.ext import commands, tasks


class Covid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        self.base_url = "https://covid-19-data.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-host': "covid-19-data.p.rapidapi.com",
            'x-rapidapi-key': cfg["rapidAPI"]["key"],
            'Accept': "application/json"
        }
        self.daily_covid_stats.start()

    def parse_covid_response(self, data: dict, location):
        # if province is in the dictionary, then we need to dig a bit deeper
        embed = discord.Embed(title=f"Covid Stats for {location}",
                              color=0x900C3F,
                              timestamp=datetime.datetime.now().astimezone())

        embed.add_field(name='Last Updated', value=f'**{get_user_friendly_date_from_string(data["lastUpdate"])}**',
                            inline=False)
        embed.add_field(name='Critical', value=f'**{parse_num(data["critical"])}**', inline=False)
        embed.add_field(name='Confirmed', value=f'**{parse_num(data["confirmed"])}**', inline=False)
        embed.add_field(name='Recovered', value=f'**{parse_num(data["recovered"])}**', inline=False)
        embed.add_field(name='Deaths', value=f'**{parse_num(data["deaths"])}**', inline=False)
        return embed

    def get_covid_stats(self, location=None):
        if location is None:
            endpoint = '/totals?format=json'
            url = self.base_url + endpoint
            title = 'the World'
        else:
            endpoint = f'/country?name={location}&format=json'
            url = self.base_url + endpoint
            title = location.capitalize()

        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            embed = self.parse_covid_response(r.json()[0], title)
            return embed

    @commands.command(name='getcovidstats', aliases=['covidcases', 'covidstats', 'getcovidcases', 'covid'],
                      help='Get the latest statistics on covid 19 by country name!. If no country is supplied '
                           'I will return global status')
    async def get_latest_global(self, ctx, location=None):
            embed = self.get_covid_stats(location=location)
            await ctx.send(embed=embed)

    @tasks.loop(hours=1)
    async def daily_covid_stats(self):
            now = datetime.datetime.now().astimezone()
            # we really only want to alert people on the day of (relative to them)
            if 0 <= now.hour < 1:
                stats = self.get_covid_stats(location='USA')
                us_politics = self.bot.get_channel(760672809730572298)
                await us_politics.send(embed=stats)

    @daily_covid_stats.before_loop
    async def before_daily_covid_stats(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Covid(bot))
