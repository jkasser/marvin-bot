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
    return fuzz.partial_ratio(correct, provided)
