import pytz
from datetime import datetime


_timezones = pytz.all_timezones


def get_all_timezones() -> list:
    return _timezones


def get_possible_timezones(user_tz: str) -> list:
    possibilities = [timezone for timezone in _timezones if user_tz.lower() in timezone.lower()]
    return possibilities


def check_if_timezone_match(possibilities: list) -> bool:
    if len(possibilities) == 1:
        return True
    else:
        return False


def get_time_in_specified_timezone(user_tz: str):
    try:
        user_tz = pytz.timezone(user_tz)
        return datetime.now(user_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        print(f'Your timezone: {user_tz}, was not valid! Please try again')


def get_date_from_epoch(timestamp: int, tz=None) -> datetime:
    if tz is None:
        ts = datetime.fromtimestamp(int(timestamp))
    else:
        ts = datetime.fromtimestamp(int(timestamp), pytz.timezone(tz))
    return ts


def pad_time_with_zero(unit: int):
    if unit < 10:
        result = '%02d' % unit
    else:
        result = str(unit)
    return result