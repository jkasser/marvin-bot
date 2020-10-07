import requests
import re
from utils.mapquest import Mapquest


class RapidWeatherAPI:

    def __init__(self, token):
        self.base_url = "https://rapidapi.p.rapidapi.com/weather"
        self.headers = {
            'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
            'x-rapidapi-key': token
        }
        self.results_parser = re.compile(r'(?<=\().+?(?=\))')

    def get_daily_weather_for_city(self, lat, long):
        query_string = {"lat":f"{lat}","lon":f"{long}","units":"imperial"}
        r = requests.get(self.base_url, headers=self.headers, params=query_string)
        if r.status_code == 200:
            data = r.json()
            weather = {}
            weather["temp"] = f'{data["main"]["temp"]}'
            weather["feels_like"] = f'{data["main"]["feels_like"]}'
            weather["min"] = f'{data["main"]["temp_min"]}'
            weather["max"] = f'{data["main"]["temp_max"]}'
            weather["humidity"] = f'{data["main"]["humidity"]}'
            weather["wind"] = f'{data["wind"]["speed"]} mph'
            weather["type"] = str(data["weather"][0]["description"]).capitalize()
            return weather

