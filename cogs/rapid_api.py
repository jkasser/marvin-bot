import requests
import re
import yaml
import discord
import datetime
from utils.mapquest import Mapquest
from discord.ext import commands


class RapidWeatherAPI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        mapquest_token = cfg["mapquest"]["key"]
        self.mapq = Mapquest(mapquest_token)
        self.base_url = "https://rapidapi.p.rapidapi.com/weather"
        self.headers = {
            'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
            'x-rapidapi-key': cfg["rapidAPI"]["key"]
        }
        self.results_parser = re.compile(r'(?<=\().+?(?=\))')

    def get_daily_weather_for_city(self, lat, long):
        query_string = {"lat": f"{lat}", "lon": f"{long}", "units": "imperial"}
        r = requests.get(self.base_url, headers=self.headers, params=query_string)
        if r.status_code == 200:
            data = r.json()
            weather = dict()
            weather["temp"] = f'{data["main"]["temp"]}'
            weather["feels_like"] = f'{data["main"]["feels_like"]}'
            weather["min"] = f'{data["main"]["temp_min"]}'
            weather["max"] = f'{data["main"]["temp_max"]}'
            weather["humidity"] = f'{data["main"]["humidity"]}'
            weather["wind"] = f'{data["wind"]["speed"]}'
            weather["type"] = str(data["weather"][0]["description"]).capitalize()
            return weather

    def get_weather_for_area(self, location):
        results = self.mapq.get_lat_long_for_location(str(location))
        forecast = self.get_daily_weather_for_city(lat=results["lat"], long=results["long"])
        if forecast is not None:
            embed = discord.Embed(title=f"Weather in {location}",
                                  color=0x87ceeb,
                                  timestamp=datetime.datetime.now().astimezone())
            embed.add_field(name="Description", value=f"**{forecast['type']}**", inline=False)
            embed.add_field(name="Temperature(F)", value=f"**{forecast['temp']}°F**", inline=False)
            embed.add_field(name="Feels Like(F)", value=f"**{forecast['feels_like']}°F**", inline=False)
            embed.add_field(name="Min Temp(F)", value=f"**{forecast['min']}°F**", inline=False)
            embed.add_field(name="Max Temp(F)", value=f"**{forecast['max']}°F**", inline=False)
            embed.add_field(name="Humidity(%)", value=f"**{forecast['humidity']}%**", inline=False)
            embed.add_field(name="Wind(MPH)", value=f"**{forecast['wind']}MPH**", inline=False)
            embed.set_thumbnail(url=results["thumb"])
            return embed

    @commands.command(name='getweather', help="Provide city/state/country/zip to get today's weather forecast!")
    async def get_todays_weather(self, ctx, query):
        if query is not None:
            embed = self.get_weather_for_area(query)
            await ctx.send(embed=embed)
        else:
            await ctx.send('Please provide a city/state or zip code.')


def setup(bot):
    bot.add_cog(RapidWeatherAPI(bot))
