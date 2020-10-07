import calendar
import re
import difflib


def get_user_friendly_date_from_string(date_string: str) -> str:
    return f'{calendar.month_name[int(date_string.split("-")[1])]} {date_string.split("-")[2].split("T")[0]}, {date_string.split("-")[0]}'


def get_slug_from_url(url):
    return f'{url.strip("/").split("/")[-1]}'


def parse_question_from_link(text):
    question = re.compile(r'(?<=\>).*(?=\<)')
    return question.search(text).group()


def parse_href_from_string(text):
    url = re.compile(r'(?<=\")http.+?(?=\\\")')
    return url.search(text).group()


def compare_answers(correct, provided):
    return float(str(difflib.SequenceMatcher(None, correct, provided).ratio())[:5])
