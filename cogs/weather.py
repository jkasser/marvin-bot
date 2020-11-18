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

    def get_daily_weather_for_city(self, lat, long, days=1, tz=None):
        query_string = {"lat": f"{lat}", "lon": f"{long}", "units": "imperial", "cnt": str(days)}
        r = requests.get(self.base_url, headers=self.headers, params=query_string)
        if r.status_code == 200:
            data = r.json()["list"]
            if int(days) == 1:
                data = data[0]
                # since we hardcode the count to b 1, this will only ever be a len 1 list
                weather = dict()
                date = get_date_from_epoch(data["dt"], tz=tz)
                sr = get_date_from_epoch(data["sunrise"], tz=tz)
                ss = get_date_from_epoch(data["sunset"], tz=tz)
                weather["date"] = f'{date}'.split(" ")[0]
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
            else:
                forecast = []
                for x in data:
                    weather = dict()
                    date = get_date_from_epoch(x["dt"], tz=tz)
                    sr = get_date_from_epoch(x["sunrise"], tz=tz)
                    ss = get_date_from_epoch(x["sunset"], tz=tz)
                    weather["date"] = f'{date}'.split(" ")[0]
                    weather["sunrise"] = f'{sr.hour}:{sr.minute}'
                    weather["sunset"] = f'{ss.hour}:{ss.minute}'
                    weather["temp"] = x["temp"]["day"]
                    weather["min"] = x["temp"]["min"]
                    weather["max"] = x["temp"]["max"]
                    weather["feels_like"] = x["feels_like"]["day"]
                    weather["feels_morn"] = x["feels_like"]["morn"]
                    weather["feels_night"] = x["feels_like"]["night"]
                    weather["humidity"] = x["humidity"]
                    weather["clouds"] = x["clouds"]
                    weather["wind"] = x["speed"]
                    weather["wind_dir"] = x["deg"]
                    weather["pop"] = x["pop"]
                    weather["type"] = str(x["weather"][0]["description"]).capitalize()
                    if 'rain' in x.keys():
                        weather["rain"] = x["rain"]
                    if 'snow' in x.keys():
                        weather["snow"] = x["snow"]
                    forecast.append(weather)
                return forecast

    def get_weather_for_area(self, * location, days=1, tz=None):
        local = " ".join(location)
        results = self.mapq.get_lat_long_for_location(str(local))
        forecast = self.get_daily_weather_for_city(lat=results["lat"], long=results["long"], days=days, tz=tz)
        if forecast is not None:
            if isinstance(forecast, dict):
                embed = discord.Embed(title=f"Weather in {local}",
                                      color=0x87ceeb,
                                      timestamp=datetime.datetime.now().astimezone())
                embed.add_field(name="Date", value=f"**{forecast['date']}**", inline=False)
                embed.add_field(name="Sunrise", value=f"**{forecast['sunrise']}**", inline=False)
                embed.add_field(name="Sunset", value=f"**{forecast['sunset']}**", inline=False)
                embed.add_field(name="Description", value=f"**{forecast['type']}**", inline=False)
                embed.add_field(name="Temperature(F)", value=f"**{forecast['temp']}°F**", inline=False)
                embed.add_field(name="Feels Like Morn(F)", value=f"**{forecast['feels_morn']}°F**", inline=False)
                embed.add_field(name="Feels Like Day(F)", value=f"**{forecast['feels_like']}°F**", inline=False)
                embed.add_field(name="Feels Like Night(F)", value=f"**{forecast['feels_night']}°F**", inline=False)
                embed.add_field(name="Min(F)", value=f"**{forecast['min']}°F**", inline=False)
                embed.add_field(name="Max(F)", value=f"**{forecast['max']}°F**", inline=False)
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
            elif isinstance(forecast, list):
                embed_list = list()
                for x in forecast:
                    embed = discord.Embed(title=f"Weather in {local}",
                                          color=0x87ceeb,
                                          timestamp=datetime.datetime.now().astimezone())
                    embed.add_field(name="Date", value=f"**{x['date']}**", inline=False)
                    embed.add_field(name="Sunrise", value=f"**{x['sunrise']}**", inline=False)
                    embed.add_field(name="Sunset", value=f"**{x['sunset']}**", inline=False)
                    embed.add_field(name="Description", value=f"**{x['type']}**", inline=False)
                    embed.add_field(name="Temperature(F)", value=f"**{x['temp']}°F**", inline=False)
                    embed.add_field(name="Feels Like Morn(F)", value=f"**{x['feels_morn']}°F**", inline=False)
                    embed.add_field(name="Feels Like Day(F)", value=f"**{x['feels_like']}°F**", inline=False)
                    embed.add_field(name="Feels Like Night(F)", value=f"**{x['feels_night']}°F**", inline=False)
                    embed.add_field(name="Min(F)", value=f"**{x['min']}°F**", inline=False)
                    embed.add_field(name="Max(F)", value=f"**{x['max']}°F**", inline=False)
                    embed.add_field(name="Cloudiness", value=f"**{x['clouds']}%**", inline=False)
                    embed.add_field(name="Chance of Precipitation", value=f"**{int(x['pop']) * 100}%**", inline=False)
                    embed.add_field(name="Humidity(%)", value=f"**{x['humidity']}%**", inline=False)
                    embed.add_field(name="Wind(MPH)", value=f"**{x['wind']}MPH** "
                                                            f"**{self.deg_to_compas(x['wind_dir'])}**", inline=False)
                    if 'snow' in x.keys():
                        embed.add_field(name="Snow Amount", value=f"**{x['snow']}mm**")
                    if 'rain' in x.keys():
                        embed.add_field(name="Rain Amount", value=f"**{x['rain']}mm**")
                    embed.set_thumbnail(url=results["thumb"])
                    embed_list.append(embed)
                return embed_list

    @commands.command(name='getweather', aliases=['weather'],
                      help='Provide city/state/country/zip to get today\'s weather forecast!')
    async def get_todays_weather(self, ctx, * location):
        #TODO:: ADD TIMEZONE HANDLING
        location = " ".join(location)
        if len(location) > 0:
            embed = self.get_weather_for_area(location, days=1)
            embed.set_footer(text=f'Requested by: {ctx.message.author.name}')
            await ctx.send(embed=embed)
        else:
            await ctx.send('Please provide a city/state or zip code.')

    @commands.command(name='getforecast', aliases=['forecast'],
                      help='Provide city/state/country/zip to get today\'s weather forecast!')
    # TODO:: ADD TIMEZONE HANDLING
    async def get_todays_forecast(self, ctx, days, * location):
        location = " ".join(location)
        if len(location) > 0:
            embed_list = self.get_weather_for_area(location, days=days)
            for embed in embed_list:
                embed.set_footer(text=f'Requested by: {ctx.message.author.name}')
                await ctx.send(embed=embed)
        else:
            await ctx.send('Error: Please type: !getforecase <# of days> <location>')


def setup(bot):
    bot.add_cog(Weather(bot))
