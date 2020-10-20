from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils import timezones
from utils.helper import check_if_valid_hour
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cogs.weather import Weather
import pytz


class AddressBook(commands.Cog, SubscriptionsDB):

    ADDRESS_TABLE_NAME = "address_book"
    ADDRESS_TABLE = f"""CREATE TABLE IF NOT EXISTS {ADDRESS_TABLE_NAME} (
        id integer PRIMARY KEY,
        user_id integer NOT NULL,
        name text NOT NULL,
        address text,
        phone text,
        birthday timestamp,
        birthday_reminder integer,
        FOREIGN KEY(user_id) REFERENCES {SubscriptionsDB.SUB_USERS_TABLE_NAME}(id)
    );"""
    INSERT_ADDRESS = f"""INSERT INTO {ADDRESS_TABLE_NAME}(user_id, name, address, phone, birthday, birthday_reminder) 
    VALUES(?,?,?,?,?,?)"""
    CHECK_IF_ENTRY_EXISTS = f"""SELECT EXISTS(SELECT * FROM {ADDRESS_TABLE_NAME} 
                                WHERE user_id=? AND name = ? LIMIT 1)"""
    GET_ADDRESS_BOOK_FOR_USER = f"""SELECT * FROM {ADDRESS_TABLE_NAME} where user_id = ?"""

    def __init__(self, bot):
        super(AddressBook, self).__init__()
        self.address_book = dict()
        self.bot = bot
        # create the address table if it doesn't exist
        self.create_table(self.conn, self.ADDRESS_TABLE)
        # get all our users
        users = self.users
        if len(users) > 0:
            for user in users:
                self.address_book[user[1]] = dict(user_id=user[0], tz=user[2], disc_id=user[3], address_book=[])
                addresses = self.get_address_book_for_user(user[0])
                for address in addresses:
                    sub_dict = dict()
                    self.address_book[user[1]]["address_book"].append(sub_dict)



    def get_address_book_for_user(self, user_id):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_ADDRESS_BOOK_FOR_USER, (user_id,))
        results = results.fetchall()
        self.conn.commit()
        return results


