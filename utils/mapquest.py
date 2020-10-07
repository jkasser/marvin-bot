import requests


class Mapquest:

    def __init__(self, token):
        self.token = token
        self.base_url = f"http://www.mapquestapi.com/geocoding/v1/address?key={self.token}"

    def get_lat_long_for_location(self, q):
        url = self.base_url + f'&location={q}&maxresults=3'
        r = requests.get(url)
        if r.status_code == 200:
            return self.parse_location_results(r.json())
        elif r.status_code == 400:
            return 'There was an error with the input, please check your query and try again'
        elif r.status_code == 403:
            return 'The provided API key has been forbidden. Please contact a developer.'
        else:
            'There was an error processing the request'

    def parse_location_results(self, response_json):
        loc = {}
        result = response_json["results"][0]["locations"][0]
        loc["lat"] = result["latLng"]["lat"]
        loc["long"] = result["latLng"]["lng"]
        loc["thumb"] = result["mapUrl"]
        return loc