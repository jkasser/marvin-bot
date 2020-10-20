import requests
import re
import yaml
import discord
import datetime
from utils.mapquest import Mapquest
from discord.ext import commands
from utils.timezones import get_date_from_epoch


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        mapquest_token = cfg["mapquest"]["key"]
        self.mapq = Mapquest(mapquest_token)
        # self.base_url = "https://rapidapi.p.rapidapi.com/weather"
        self.base_url = "https://rapidapi.p.rapidapi.com/forecast/daily"
        self.headers = {
            'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
            'x-rapidapi-key': cfg["rapidAPI"]["key"]
        }
        self.results_parser = re.compile(r'(?<=\().+?(?=\))')

    def deg_to_compas(self, num):
        val = int((num / 22.5) + .5)
        arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return (arr[(val % 16)])

    def get_daily_weather_for_city(self, lat, long):
        query_string = {"lat": f"{lat}", "lon": f"{long}", "units": "imperial", "cnt": "1"}
        r = requests.get(self.base_url, headers=self.headers, params=query_string)
        if r.status_code == 200:
            # since we hardcode the count to b 1, this will only ever be a len 1 list
            data = r.json()["list"][0]
            weather = dict()
            sr = get_date_from_epoch(data["sunrise"])
            ss = get_date_from_epoch(data["sunset"])
            weather["sunrise"] = f'{sr.hour}:{sr.minute}'
            weather["sunset"] = f'{ss.hour}:{ss.minute}'
            weather["temp"] = data["temp"]["day"]
            weather["min"] = data["temp"]["min"]
            weather["max"] = data["temp"]["max"]
            weather["feels_like"] = data["feels_like"]["day"]
            weather["feels_morn"] = data["feels_like"]["morn"]
            weather["feels_night"] = data["feels_like"]["night"]
            weather["humidity"] = data["humidity"]
            weather["clouds"] = data["clouds"]
            weather["wind"] = data["speed"]
            weather["wind_dir"] = data["deg"]
            weather["pop"] = data["pop"]
            weather["type"] = str(data["weather"][0]["description"]).capitalize()
            if 'rain' in data.keys():
                weather["rain"] = data["rain"]
            if 'snow' in data.keys():
                weather["snow"] = data["snow"]
            return weather

    def get_weather_for_area(self, * location):
        local = " ".join(location)
        results = self.mapq.get_lat_long_for_location(str(local))
        forecast = self.get_daily_weather_for_city(lat=results["lat"], long=results["long"])
        if forecast is not None:
            embed = discord.Embed(title=f"Weather in {local}",
                                  color=0x87ceeb,
                                  timestamp=datetime.datetime.now().astimezone())
            embed.add_field(name="Description", value=f"**{forecast['type']}**", inline=False)
            embed.add_field(name="Temperature(F)", value=f"**{forecast['temp']}°F**", inline=False)
            embed.add_field(name="Feels Like Day(F)", value=f"**{forecast['feels_like']}°F**", inline=False)
            embed.add_field(name="Feels Like Morn(F)", value=f"**{forecast['feels_morn']}°F**", inline=False)
            embed.add_field(name="Feels Like Night(F)", value=f"**{forecast['feels_night']}°F**", inline=False)
            embed.add_field(name="Min Temp(F)", value=f"**{forecast['min']}°F**", inline=False)
            embed.add_field(name="Max Temp(F)", value=f"**{forecast['max']}°F**", inline=False)
            embed.add_field(name="Cloudiness", value=f"**{forecast['clouds']}%**", inline=False)
            embed.add_field(name="Chance of Precipitation", value=f"**{int(forecast['pop']) * 100}%**", inline=False)
            embed.add_field(name="Humidity(%)", value=f"**{forecast['humidity']}%**", inline=False)
            embed.add_field(name="Wind(MPH)", value=f"**{forecast['wind']}MPH** "
                                                    f"**{self.deg_to_compas(forecast['wind_dir'])}**", inline=False)
            if 'snow' in forecast.keys():
                embed.add_field(name="Snow Amount", value=f"**{forecast['snow']}mm**")
            if 'rain' in forecast.keys():
                embed.add_field(name="Rain Amount", value=f"**{forecast['rain']}mm**")
            embed.set_thumbnail(url=results["thumb"])
            return embed

    @commands.command(name='getweather', help="Provide city/state/country/zip to get today's weather forecast!")
    async def get_todays_weather(self, ctx, * location):
        location = " ".join(location)
        if len(location) > 0:
            embed = self.get_weather_for_area(location)
            embed.set_footer(text=f'Requested by: {ctx.message.author.name}')
            await ctx.send(embed=embed)
        else:
            await ctx.send('Please provide a city/state or zip code.')


def setup(bot):
    bot.add_cog(Weather(bot))
