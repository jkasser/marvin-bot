from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils import timezones
from utils.helper import check_if_valid_hour
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cogs.rapid_api import RapidWeatherAPI
import pytz


class AddressBook(commands.Cog, SubscriptionsDB):