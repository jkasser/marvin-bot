import calendar


def get_user_friendly_date_from_string(date_string: str) -> str:
    return f'{calendar.month_name[int(date_string.split("-")[1])]} {date_string.split("-")[2].split("T")[0]}, {date_string.split("-")[0]}'


def get_slug_from_url(url):
    return f'{url.strip("/").split("/")[-1]}'