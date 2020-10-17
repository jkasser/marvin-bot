from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils import timezones
from utils.helper import check_if_valid_hour
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cogs.rapid_api import RapidWeatherAPI
import pytz


class Subscriptions(commands.Cog, SubscriptionsDB):

    SUB_USERS_TABLE_NAME = "users"
    SUB_USERS_TABLE = f"""CREATE TABLE IF NOT EXISTS {SUB_USERS_TABLE_NAME} (
        id integer PRIMARY KEY,
        user text NOT NULL,
        timezone text NOT NULL,
        disc_id integer NOT NULL
    );"""
    INSERT_USER = f"""INSERT INTO {SUB_USERS_TABLE_NAME}(user, timezone, disc_id) VALUES(?,?,?)"""
    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {SUB_USERS_TABLE_NAME} WHERE user=? LIMIT 1)"""
    GET_USER = f"""SELECT * FROM {SUB_USERS_TABLE_NAME} WHERE user=? LIMIT 1"""
    GET_ALL_USERS = f"""SELECT * FROM {SUB_USERS_TABLE_NAME}"""

    SUBSCRIPTION_TABLE_NAME = "subs"
    SUBSCRIPTION_TABLE = f"""CREATE TABLE IF NOT EXISTS {SUBSCRIPTION_TABLE_NAME} (
        id integer PRIMARY KEY,
        user_id integer NOT NULL,
        sub_type text NOT NULL,
        sub_details text NOT NULL,
        when_send integer NOT NULL,
        active integer NOT NULL,
        last_sent timestamp,
        FOREIGN KEY(user_id) REFERENCES {SUB_USERS_TABLE_NAME}(id)
    );"""
    INSERT_SUB = f"""INSERT INTO {SUBSCRIPTION_TABLE_NAME}(user_id, sub_type, sub_details, when_send, active, last_sent) 
    VALUES(?,?,?,?,?,?)"""
    CHECK_IF_SUB_EXISTS = f"""SELECT EXISTS(SELECT * FROM {SUBSCRIPTION_TABLE_NAME} 
                                WHERE user_id=? AND sub_type = ? LIMIT 1)"""
    UPDATE_SUB_LAST_SENT = f"""UPDATE {SUBSCRIPTION_TABLE_NAME} SET last_sent = ? where id = ?"""
    UPDATE_SUB_ACTIVE_STATUS = f"""UPDATE {SUBSCRIPTION_TABLE_NAME} SET active = ? where id = ?"""
    GET_ALL_SUBS = f"""SELECT * FROM {SUBSCRIPTION_TABLE_NAME} GROUP BY user_id"""
    GET_ACTIVE_SUBS_BY_USER_ID = f"""SELECT * FROM {SUBSCRIPTION_TABLE_NAME} WHERE active = 1 AND user_id = ?"""
