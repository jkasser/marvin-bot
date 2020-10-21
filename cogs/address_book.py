from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils import timezones
from utils.helper import check_if_valid_hour, parse_string_to_datetime, turn_datetime_into_string
from utils.helper import decode_value, encode_value, map_active_to_bool, map_bool_to_active
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz


class AddressBook(commands.Cog, SubscriptionsDB):

    ADDRESS_TABLE_NAME = "address_book"
    ADDRESS_TABLE = f"""CREATE TABLE IF NOT EXISTS {ADDRESS_TABLE_NAME} (
        id integer PRIMARY KEY,
        user_id integer NOT NULL,
        name text NOT NULL,
        address text,
        phone text,
        email text,
        birthday timestamp,
        birthday_reminder integer,
        FOREIGN KEY(user_id) REFERENCES {SubscriptionsDB.SUB_USERS_TABLE_NAME}(id)
    );"""
    GET_ADDRESS_BOOK_FOR_USER = f"""SELECT * FROM {ADDRESS_TABLE_NAME} where user_id = ?"""
    DELETE_ENTRY_FOR_USER = f"""DELETE FROM {ADDRESS_TABLE_NAME} WHERE id = ? AND user_id = ?"""
    GET_ENTRY_FOR_USER = F""" SELECT * FROM {ADDRESS_TABLE_NAME} WHERE name LIKE ? AND user_id = ?"""

    UPDATE_ENTRY_FOR_USER = f"""UPDATE {ADDRESS_TABLE_NAME} SET name = ?, address = ?, phone = ?, email = ?, 
                            birthday = ?, birthday_reminder = ?, WHERE name LIKE ? AND user_id = ?"""
    CHECK_IF_ENTRY_EXISTS = f"""SELECT EXISTS(SELECT * FROM {ADDRESS_TABLE_NAME} 
                                    WHERE user_id=? AND name = ? LIMIT 1)"""
    INSERT_CONTACT = f"""INSERT INTO {ADDRESS_TABLE_NAME} (user_id, name, address, phone, email, birthday, birthday_reminder) 
                        VALUES(?,?,?,?,?,?,?)"""
    DELETE_CONTACT = F"""DELETE FROM {ADDRESS_TABLE_NAME} WHERE id = ?"""

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
                    # the info will be stored encoded
                    contact_info = dict(
                        id=address[0],
                        name=decode_value(address[2]),
                        address=decode_value(address[3]),
                        phone=decode_value(address[4]),
                        email=decode_value(address[5]),
                        birthday=address[6],
                        bday_reminder=address[7]
                    )
                    self.address_book[user[1]]["address_book"].append(contact_info)

    def get_address_book_for_user(self, user_id):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_ADDRESS_BOOK_FOR_USER, (user_id,))
        results = results.fetchall()
        self.conn.commit()
        return results

    def update_address_book_for_user(self, user_id, entry_name, field, value):
        # expects, field, value, entry_name, user_id in that order
        self.update_query(self.UPDATE_ENTRY_FOR_USER, (field, value, f'%{entry_name}%', user_id,))

    # This could potentially be rate limited by the amount of message it would send... commenting out for now
    # @commands.command(name='contactgetall', help='Get your address book!')
    # async def get_address_book(self, ctx):
    #     user = str(ctx.author)
    #     pass

    @commands.command(name='contactget', help='Get one entry from your address book!')
    async def get_contact_by_name(self, ctx, * contact_name):
        user = str(ctx.author)
        contact_name = " ".join(contact_name)
        if contact_name == "":
            await ctx.send('Please provide a name to search for!')
            return
        else:
            await ctx.send(f'Looking up {contact_name}...')
            if user in self.address_book.keys():
                channel = await ctx.author.create_dm()
                potential_hits = [contact for contact in self.address_book[user]["address_book"] if contact_name.lower() in contact["name"].lower()]
                if len(potential_hits) > 0:
                    await ctx.send(f'I have found {len(potential_hits)} matche(s) and '
                                   f'will send the relevant info to you via a direct message!')
                    for hit in potential_hits:
                        msg = f'{contact_name}\'s Information:\n'
                        for field, value in hit.items():
                            if field.lower() == 'birthday':
                                value = turn_datetime_into_string(value)
                            elif field.lower() == 'birthday_reminder':
                                field = 'Birthday Reminders'
                                value = map_bool_to_active(int(value))
                            msg += f'{str(field).capitalize()}: {str(value)}\n'
                        await channel.send(msg)
                else:
                    # we can't find anyone
                    await ctx.send(f'Sorry! I was unable to find a contact by the name of {contact_name}.')
            else:
                await ctx.send('Before you can use my address book feature, I need to get your timezone (for reminders)! '
                               'Please type "!subsettz" to set your timezone with me, and then try adding a contact with'
                               '"!contactadd".')

    @commands.command(name='contactadd', help='Add an entry to your address book!')
    async def insert_contact(self, ctx, * contact_name):
        timeout=60
        user = str(ctx.author)
        contact_name = " ".join(contact_name)
        def check(m):
            return m.author.name == ctx.author.name
        if user in self.address_book.keys():
            if contact_name == "":
                await ctx.send('Please provide a name for the new contact!')
                return
            else:
                try:
                    # it's possible a user does this right after sub set tz, at which point we won't have this list available
                    if "address_book" not in self.address_book[user].keys():
                        # create this in memory
                        self.address_book[user]["address_book"] = []
                    else:
                        # If an address book is present, see if the contact already exists
                        potential_hits = [contact for contact in self.address_book[user]["address_book"] if contact_name.lower() in contact["name"].lower()]
                        if len(potential_hits) > 0:
                            await ctx.send(f'I have found {len(potential_hits)} possible matche(s) already in your contact.'
                                           f'Are you sure this is a new contact? Y/N')
                            confirm_name = await self.bot.wait_for("message", check=check, timeout=timeout)
                            # if the name is correct then let's create an entry
                            if confirm_name.content.lower().strip() not in ['y', 'yes']:
                                await ctx.send('No problem, you can always search for a contact with !getcontact to be sure. '
                                               'Just call !contact add whenever you are ready to try again!')
                                # bail out
                                return
                    # store the address book as a variable to make it easier to work with
                    contact_info = self.address_book[user]["address_book"]
                    # check if the name provided is correct
                    await ctx.send(f'Ok! Let\'s add {contact_name.capitalize()} to your address book!\nIs the name correct? Y/N')
                    confirm_name = await self.bot.wait_for("message", check=check, timeout=timeout)
                    # if the name is correct then let's create an entry
                    if confirm_name.content.lower().strip() in ['y', 'yes']:
                        # create the dict in the address book to start
                        #dict(id=address[0], name=address[2], address=address[3], phone=address[4],
                                            # email=address[5], birthday=address[6], bday_reminder=address[7])
                        await ctx.send('Great! I will now gather info about your contact. If you don\'t have or don\'t wish'
                                       'to provide the requested info (it will be hashed when stored), just reply "skip".\n'
                                       'I will now DM you for the following information in order to preserve your privacy.')
                        channel = await ctx.author.create_dm()
                        await channel.send('Could you please provide the address? If you wish to skip any of the fields, just reply'
                                     'with "skip".')
                        addr_response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        addr_response = addr_response.content
                        # if they choose to skip we just need to store a blank string
                        if addr_response.lower().strip() == 'skip':
                            addr_response = ""
                            await channel.send('Skipping address!')
                        # phone
                        await channel.send('Contact\'s phone number?')
                        phone_response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        phone_response = phone_response.content
                        if phone_response.lower().strip() == 'skip':
                            phone_response = ""
                            await channel.send('Skipping phone!')
                        # email
                        await channel.send('Contact\'s email?')
                        email_response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        email_response = email_response.content
                        if email_response.lower().strip() == 'skip':
                            email_response = ""
                            await channel.send('Skipping email!')
                        # email
                        await channel.send('Contact\'s birthday? (MM/DD/YYYY)\nIf year isn\'t provided I will default '
                                           'to the current year')
                        bday_response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        bday_response = bday_response.content
                        if bday_response.lower().strip() == 'skip':
                            bday_response = None
                            bday_reminder_response = 0
                            await channel.send('Skipping birthday!')
                        else:
                            bday_response = parse_string_to_datetime(bday_response)
                            if isinstance(bday_response, datetime):
                                # if they provide a birthday then we should ask if they want a reminder
                                await channel.send('Would you like me to remind you on their birthday? Y/N')
                                bday_reminder_response = await self.bot.wait_for("message", check=check, timeout=timeout)
                                bday_reminder_response = bday_reminder_response.content
                                if bday_reminder_response.lower().strip() == 'skip' or bday_reminder_response.lower().strip() in ['no', 'n']:
                                    bday_reminder_response = 0
                                    await channel.send('Someone\'s not that important are they?')
                                else:
                                    bday_reminder_response = 1
                            else:
                                await channel.send('I was unable to parse your provided birthday, I will continue but leave it blank.')
                                bday_response = None
                                bday_reminder_response = 0
                        # OK FINALLY create the entry in the book
                        contact_dict = {
                            "name": contact_name.capitalize(),
                            "address": addr_response,
                            "phone": phone_response,
                            "email": email_response,
                        }
                        # It will be none if we couldn't parse a birthday or they chose to skip, if it's set
                        if bday_response is not None:
                            contact_dict["birthday"] = bday_response
                            contact_dict["birthday_reminder"] = bday_reminder_response
                        # now append it! we are done!
                        contact_info.append(contact_dict)
                        await channel.send(f'I have successfully added {contact_name.capitalize()} to your address book!')
                        return
                    else:
                        # if it's incorrect then bail out
                        await ctx.send('Ok! Just call "!contactadd" when you are ready to try again! Good-bye!')
                        return
                except TimeoutError:
                    await ctx.send('You took too long to reply! Please try again!')
        else:
            await ctx.send('Before you can use my address book feature, I need to get your timezone (for reminders)! '
                           'Please type "!subsettz" to set your timezone with me, and then try adding a contact with'
                           '"!contactadd".')


    @commands.command(name='contactdelete', help='Remove a contact by their name.')
    async def delete_contact(self, ctx, * contact_name):
        user = str(ctx.author)
        contact_name = " ".join(contact_name)
        if user in self.address_book.keys():
            pass
        else:
            await ctx.send('Before you can use my address book feature, I need to get your timezone (for reminders)! '
                           'Please type "!subsettz" to set your timezone with me, and then try adding a contact with'
                           '"!contactadd".')

    @commands.command(name='contactupdate', help='Update a contact by their name.')
    async def update_contact(self, ctx, * contact_name):
        user = str(ctx.author)
        contact_name = " ".join(contact_name)
        if user in self.address_book.keys():
            pass
        else:
            await ctx.send('Before you can use my address book feature, I need to get your timezone (for reminders)! '
                           'Please type "!subsettz" to set your timezone with me, and then try adding a contact with'
                           '"!contactadd".')


# TODO::: Insert, Update, Delete commands. Tasks loop for updates (determine when to update and how)
# TODO::: add loop to check birthday stuff
# TODO::: on insert into DB make sure to use encode



def setup(bot):
    bot.add_cog(AddressBook(bot))
