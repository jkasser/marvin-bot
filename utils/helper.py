import calendar
import re
import difflib
from io import StringIO
from html.parser import HTMLParser
from fuzzywuzzy import fuzz


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


def get_slug_from_url(url):
    return f'{url.strip("/").split("/")[-1]}'


def link_grabber(text):
    link_text = re.compile(r'(?<=\")http.+?(?=\")')
    return link_text.findall(text)


def compare_answers(correct, provided):
    return float(str(difflib.SequenceMatcher(None, correct, provided).ratio())[:5])


def fuzz_compare_answers(correct, provided):
    return fuzz.token_set_ratio(correct, provided)


def update_leaderboard(leaderboard:list, current_player, current_value):
    """expects a list of dicts"""
    for item in leaderboard:
        for player, value in item.items():
            if current_player == player:
                addition = int(current_value.split('$')[1].replace(',', ''))
                new_value = f"${int(value.split('$')[1]) + int(addition)}"
                item[player] = new_value
                return new_value


def check_if_user_in_leaderboard(leaderboard: list, player_to_check):
    """ expects a list of dicts """
    if not any(standing[player_to_check] for standing in leaderboard):
        return False
    else:
        return True

def get_current_player_from_leaderboard(leaderboard:list, player_to_get):
    for standing in leaderboard:
        for player, worth in standing.items():
            if player == player_to_get:
                return worth