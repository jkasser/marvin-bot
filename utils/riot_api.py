import yaml
import requests
from datetime import datetime
from pytz import reference
import os


class Riot:

    def __init__(self):
        file = open(os.path.dirname(os.path.dirname(__file__)) + '/config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        region = cfg["utils"]["region"]
        self.key = cfg["utils"]["key"]
        self.base_url = f'https://{region}.api.riotgames.com/lol/'

    def get_clash_schedule(self):
        endpoint = self.base_url + f'clash/v1/tournaments?api_key={self.key}'
        r = requests.get(endpoint)
        if r.status_code == 200:
            schedule = [f'All timezones are in {reference.LocalTimezone().tzname(datetime.utcnow())}']
            for x in r.json():
                name = x["nameKey"].capitalize() + ' ' + ' '.join(x["nameKeySecondary"].split('_')).capitalize()
                registration = datetime.fromtimestamp(x["schedule"][0]["registrationTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                start_time = datetime.fromtimestamp(x["schedule"][0]["startTime"] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                is_cancelled = x["schedule"][0]["cancelled"]
                if is_cancelled:
                    is_cancelled = 'Unfortunately, yes :('
                else:
                    is_cancelled = 'No'
                schedule.append(f'Tournament: {name}\nRegistration Date: {registration}\nStart Time: {start_time}\nHas it been cancelled? {is_cancelled}\n')
            response = '\n'.join(sorted(schedule))
        else:
            response = r.status_code, r.text
        return response
