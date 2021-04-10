import calendar
import re
import difflib
import base64
from io import StringIO
from html.parser import HTMLParser
from fuzzywuzzy import fuzz
from dateutil import parser
from datetime import datetime
from utils.enums import *


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = HTMLStripper()
    s.feed(html)
    return s.get_data()


def get_user_friendly_date_from_string(date_string: str) -> str:
    return f'{calendar.month_name[int(date_string.split("-")[1])]} {date_string.split("-")[2].split("T")[0]}, {date_string.split("-")[0]}'


def turn_datetime_into_string(datetime_object) -> str:
    return datetime_object.strftime('%m/%d/%Y')


def get_turning_age_from_date_str(date_str: str):
    split_date = date_str.split('/')
    print(split_date)
    if len(split_date) == 3:
        current_year = 2021
        age = current_year - int(split_date[2])
        return age


def get_slug_from_url(url):
    return f'{url.strip("/").split("/")[-1]}'.replace('-', '')[:10]


def link_grabber(text):
    link_text = re.compile(r'(?<=\")http.+?(?=\")')
    return link_text.findall(text)


def compare_answers(correct, provided):
    return float(str(difflib.SequenceMatcher(None, correct, provided).ratio())[:5])


def fuzz_compare_answers(correct, provided):
    return fuzz.token_set_ratio(correct, provided)


def update_current_worth(leaderboard: dict, current_player, current_value):
    for player, value in leaderboard.items():
        if current_player == player:
            addition = int(current_value.split('$')[1].replace(',', ''))
            new_value = f"${int(value.split('$')[1]) + int(addition)}"
            leaderboard[player] = new_value
            return new_value


def check_if_valid_hour(supplied_hour: str):
    try:
        hour = int(supplied_hour)
        if 1 <= hour <= 24:
            return True
        else:
            return False
    except ValueError:
        return False


def encode_value(value: str):
    return base64.b64encode(value.encode('utf-8')).decode()


def decode_value(value: str):
    return base64.b64decode(value.encode('utf-8')).decode()


def parse_string_to_datetime(date):
    return parser.parse(date)


def map_bool_to_active(bool_value: int) -> str:
    return ACTIVE_ENUM[int(bool_value)]


def map_active_to_bool(active_or_inactive: str) -> int:
    for k, v in ACTIVE_ENUM.items():
        if active_or_inactive.lower().strip() == v:
            return k


def get_current_hour_of_day():
    return datetime.now().astimezone().hour


def parse_num(number):
    if number != None:
        return '{:,}'.format(number)
    else:
        return 'None'


def validate_phone_number(number):
    number_check = re.compile(r'^\+\d{11}$')
    try:
        number_check.search(number).group()
        return True
    except AttributeError:
        return False
