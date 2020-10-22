from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils.helper import parse_string_to_datetime, turn_datetime_into_string
from utils.helper import decode_value, encode_value, map_active_to_bool, map_bool_to_active
from utils.enums import ACTIVE_ENUM
from datetime import datetime
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
                            birthday = ?, birthday_reminder = ? WHERE id = ? AND user_id = ?"""
    CHECK_IF_ENTRY_EXISTS = f"""SELECT EXISTS(SELECT * FROM {ADDRESS_TABLE_NAME} 
                                    WHERE user_id=? AND name = ? LIMIT 1)"""
    INSERT_CONTACT = f"""INSERT INTO {ADDRESS_TABLE_NAME} (user_id, name, address, phone, email, birthday, 
                    birthday_reminder) VALUES(?,?,?,?,?,?,?)"""
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
                        name=address[2],
                        address=decode_value(address[3]),
                        phone=decode_value(address[4]),
                        email=decode_value(address[5]),
                        birthday=address[6],
                        birthday_reminder=address[7]
                    )
                    self.address_book[user[1]]["address_book"].append(contact_info)
        self.check_birthday_notification.start()
        self.insert_or_update_contacts_in_database.start()

    def get_address_book_for_user(self, user_id):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_ADDRESS_BOOK_FOR_USER, (user_id,))
        results = results.fetchall()
        self.conn.commit()
        return results

    def insert_contact_into_db(self, user_id, name, address, phone, email, birthday, birthday_reminder):
        values = (
            user_id, name, encode_value(address), encode_value(phone), encode_value(email),
            birthday, birthday_reminder,
        )
        contact_id = self.insert_query(self.INSERT_CONTACT, values)
        return contact_id

    def update_contact_by_user_id_and_contact_id(self, user_id, name, address, phone, email, birthday,
                                                 birthday_reminder, contact_id):
        # this needs to go in the order of:
        # name, address, phone, email, birthday, birthday_reminder
        # then the where clause of name and user_id. name needs to be wrapped in %% for a like clause
        values = (
            name, encode_value(address), encode_value(phone), encode_value(email),
            birthday, birthday_reminder, contact_id, user_id,)
        self.update_query(self.UPDATE_ENTRY_FOR_USER, values)

    def delete_contact_by_id(self, contact_id):
        self.delete_query(self.DELETE_CONTACT, (contact_id,))

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
            await ctx.send(f'Looking up {contact_name.capitalize()}...')
            if user in self.address_book.keys():
                channel = await ctx.author.create_dm()
                potential_hits = [contact for contact in self.address_book[user]["address_book"]
                                  if contact_name.lower() in contact["name"].lower()]
                if len(potential_hits) > 0:
                    await ctx.send(f'I have found {len(potential_hits)} matche(s) and '
                                   f'will send the relevant info to you via a direct message!')
                    for hit in potential_hits:
                        msg = f'{hit["name"].capitalize()}\'s Information:\n'
                        for field, value in hit.items():
                            if field.lower() == 'birthday' and value is not None:
                                value = turn_datetime_into_string(value)
                            else:
                                value = ""
                            if field.lower() == 'birthday_reminder':
                                field = 'Birthday Reminders'
                                value = map_bool_to_active(int(value))
                            msg += f'{str(field).capitalize()}: {str(value)}\n'
                        # add a blank line between entries
                        msg += '\n'
                        await channel.send(msg)
                else:
                    # we can't find anyone
                    await ctx.send(f'Sorry! I was unable to find a contact by the name of {contact_name}.')
            else:
                await ctx.send('Before you can use my address book feature, I need to get your timezone '
                               '(for reminders)! Please type "!subsettz" to set your timezone with me, and then try '
                               'adding a contact with "!contactadd".')

    @commands.command(name='contactadd', help='Add an entry to your address book!')
    async def add_contact(self, ctx, * contact_name):
        timeout = 60
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
                    # it's possible a user does this right after sub set tz
                    # at which point we won't have this list available
                    if "address_book" not in self.address_book[user].keys():
                        # create this in memory
                        self.address_book[user]["address_book"] = []
                    else:
                        # If an address book is present, see if the contact already exists
                        potential_hits = [contact for contact in self.address_book[user]["address_book"]
                                          if contact_name.lower() in contact["name"].lower()]
                        if len(potential_hits) > 0:
                            await ctx.send(f'I have found {len(potential_hits)} possible matche(s) '
                                           f'already in your contacts. Are you sure this is a new contact? Y/N')
                            confirm_name = await self.bot.wait_for("message", check=check, timeout=timeout)
                            # if the name is correct then let's create an entry
                            if confirm_name.content.lower().strip() not in ['y', 'yes']:
                                await ctx.send('No problem, you can always search for a contact with '
                                               '!getcontact to be sure. Just call !contactadd whenever you are '
                                               'ready to try again!')
                                # bail out
                                return
                    # store the address book as a variable to make it easier to work with
                    contact_info = self.address_book[user]["address_book"]
                    # check if the name provided is correct
                    await ctx.send(f'Ok! Let\'s add {contact_name.capitalize()} to your address book!'
                                   f'\nIs the name correct? Y/N')
                    confirm_name = await self.bot.wait_for("message", check=check, timeout=timeout)
                    # if the name is correct then let's create an entry
                    if confirm_name.content.lower().strip() in ['y', 'yes']:
                        # create the dict in the address book to start
                        # dict(id=address[0], name=address[2], address=address[3], phone=address[4],
                        # email=address[5], birthday=address[6], bday_reminder=address[7])
                        await ctx.send('Great! I will now gather info about your contact. If you don\'t have '
                                       'or don\'t wish to provide the requested info (it will be hashed when stored),'
                                       ' just reply "skip".\nI will now DM you for the following information in order'
                                       ' to preserve your privacy.')
                        channel = await ctx.author.create_dm()
                        await channel.send('Could you please provide the address? If you wish to skip '
                                           'any of the fields, just reply with "skip".')
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
                            try:
                                bday_response = parse_string_to_datetime(bday_response)
                            except Exception:
                                bday_response = ""
                            if isinstance(bday_response, datetime):
                                # if they provide a birthday then we should ask if they want a reminder
                                await channel.send('Would you like me to remind you on their birthday? Y/N')
                                bday_reminder_response = await self.bot.wait_for(
                                    "message", check=check, timeout=timeout
                                )
                                bday_reminder_response = bday_reminder_response.content
                                if bday_reminder_response.lower().strip() == 'skip' or \
                                        bday_reminder_response.lower().strip() in ['no', 'n']:
                                    bday_reminder_response = 0
                                    await channel.send('Someone\'s not that important are they?')
                                else:
                                    bday_reminder_response = 1
                            else:
                                await channel.send('I was unable to parse your provided birthday,'
                                                   ' I will continue but leave it blank.')
                                bday_response = ""
                                bday_reminder_response = 0
                        # OK FINALLY create the entry in the book
                        contact_dict = {
                            "name": contact_name.capitalize(),
                            "address": addr_response,
                            "phone": phone_response,
                            "email": email_response,
                            "birthday": bday_response,
                            "birthday_reminder": bday_reminder_response
                        }
                        # now append it! we are done!
                        contact_info.append(contact_dict)
                        await channel.send(f'I have successfully added '
                                           f'{contact_name.capitalize()} to your address book!')
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
    async def delete_contact(self, ctx, contact_id=None):
        user = str(ctx.author)
        if contact_id is None:
            await ctx.send('You must supply an ID of the contact to delete! If you don\'t see an ID yet then give it '
                           'a few minutes while I update my database! Once an ID is present you can update the '
                           'applicable contact.')
            return
        try:
            contact_id = int(contact_id)
        except ValueError:
            await ctx.send('The ID must be a whole number! Please try again.')
            return
        if user in self.address_book.keys():
            # check if they have any contacts
            if len(self.address_book[user]["address_book"]) == 0:
                await ctx.send('You have no contacts! Add some with !contactadd.')
                return
            else:
                # if they have contacts let's get the contact - do a str compare on ID since it could be an empty string
                contact = [contact for contact in self.address_book[user]["address_book"] if
                           int(contact["id"]) == int(contact_id) if "id" in contact.keys()]
                if len(contact) == 0:
                    await ctx.send(f'I wasn\'t able to find a contact that matched ID: {contact_id}. It takes me a couple'
                                   f' minutes to update my database which is where I get the ID from. You can always '
                                   f'do a !contactget <contact name> to see if that contact exists and what their ID '
                                   f'is!')
                    return
                elif len(contact) > 1:
                    await ctx.send(f'Somehow I have found {len(contact)} matches. Please contact an admin.')
                    return
                else:
                    contact = contact[0]
                    await ctx.send(f'Deleting entry for {contact["name"]}!')
                    del self.address_book[user]["address_book"][self.address_book[user]["address_book"].index(contact)]
                    # now delete from the database as well
                    self.delete_contact_by_id(int(contact_id))
                    await ctx.send('Contact deleted!')

    @commands.command(name='contactupdate', help='Update a contact by their name.')
    async def update_contact(self, ctx, contact_id=None, field=None, value=None):
        user = str(ctx.author)
        if contact_id is None:
            await ctx.send('You must supply an ID of the contact to update! If you don\'t see an ID yet then give it '
                           'a few minutes while I update my database! Once an ID present you can update the '
                           'applicable contact. The ID must be an integer!')
            return
        elif field is None:
            await ctx.send('You must supply the field you wish to update, e.g. name/phone/address/email/birthday')
            return
        elif value is None:
            await ctx.send(f'You must supply the new value that I should update {field} to!')
            return
        elif field.lower() in 'bday_reminder':
            try:
                map_active_to_bool(value.lower())
            except ValueError:
                await ctx.send(f'The supplied value {value} failed validation. I can only accept the following values '
                               f'for the birthday reminder field: {", ".join(ACTIVE_ENUM.values())}')
        elif field.lower() == 'id':
            await ctx.send('You cannot update the ID of a record!')
            return
        elif field.lower() in 'birthday':
            try:
                potential_bday = parse_string_to_datetime(value)
            except Exception:
                potential_bday = None
            if not isinstance(potential_bday, datetime):
                await ctx.send(f'The format of {value} was not correct.'
                               f' Please supply a birthday in the format of MM/DD/YYYY.')
                return
        try:
            contact_id = int(contact_id)
        except ValueError:
            await ctx.send('The ID must be a whole number! Please try again.')
            return
        # ok check if the user exists
        if user in self.address_book.keys():
            # check if they have any contacts
            if len(self.address_book[user]["address_book"]) == 0:
                await ctx.send('You have no contacts! Add some with !contactadd.')
                return
            else:
                # if they have contacts let's get the contact - do a str compare on ID since it could be an empty string
                contact = [contact for contact in self.address_book[user]["address_book"]
                           if int(contact["id"]) == int(contact_id) if "id" in contact.keys()]
                if len(contact) == 0:
                    await ctx.send(f'I wasn\'t able to find a contact that matched ID: {contact_id}. It takes me a '
                                   f'couple minutes to update my database which is where I get the ID from. '
                                   f'You can always do a !contactget <contact name> to see if that contact exists '
                                   f'and what their ID is!')
                    return
                elif len(contact) > 1:
                    await ctx.send(f'Somehow I have found {len(contact)} matches. Please contact an admin.')
                    return
                else:
                    contact = contact[0]
                    # since ID is a primary key it will always be unique
                    if field.lower() == 'birthday':
                        str_value = value
                        value = parse_string_to_datetime(value)
                    # this comes after and takes reminder as well as an option
                    elif field.lower() in 'birthday_reminder':
                        str_value = value
                        value = map_active_to_bool(value.lower())
                    else:
                        str_value = value
                    if field.lower() in contact.keys():
                        contact[field.lower()] = value
                        # now we also want to set the update flag to True here
                        contact["update_pending"] = True
                        await ctx.send(f'Great! I have updated the {field} to {str_value}.')
                        return
                    else:
                        await ctx.send(f'I could\'t find a valid field for: {field}. Here are the fields I have '
                                       f'available to update: '
                        f'{", ".join([key for key in contact.keys() if key != "id" if key != "update_pending"])}')
                        return
        else:
            await ctx.send('It looks like this is your first time using my address book feature! Please call'
                           '!subsettz to set your timezone. Then you will want to add contacts before you have'
                           'something to update.')

    @tasks.loop(minutes=3)
    async def insert_or_update_contacts_in_database(self):
        for user, info in self.address_book.items():
            if "user_id" not in info.keys():
                # if the user isn't in the database we need to add him first with TZ info and get his user_id for the
                if not self.check_if_user_exists(user):
                    # insert the user and the timezone
                    user_id = self.insert_user(user, info["tz"], info["disc_id"])
                    # add this key to the dict in memory now
                    info["user_id"] = user_id
                    # if they aren't in the dictionary in memory, and not in the database, then something else broke
                else:
                    user_id = self.get_user(user)[0][0]
            else:
                # their id is stored in memory so we can just grab the user id from there
                user_id = info["user_id"]
            # if address_book isnt in info.keys then the user has just set their tz, not created any subscriptions yet
            if "address_book" in info.keys():
                # now get every contact in the database
                for contact in info["address_book"]:
                    if "id" not in contact.keys():
                        # then we know we have to insert into the database
                        # expects: user_id, name, address, phone, email, birthday, birthday_reminder
                        # encoding happens within the insert contact method, so leave them as strings here
                        contact_id = self.insert_contact_into_db(
                            user_id, contact["name"], contact["address"], contact["phone"], contact["email"],
                            contact["birthday"], int(contact["birthday_reminder"])
                        )
                        # set the contact ID in the dict <- from this point on users can update/delete contacts
                        contact["id"] = contact_id
                    elif "update_pending" in contact.keys() and contact["update_pending"]:
                        # if id is in keys then lets try to update the contact
                        # expects: user_id, name, address, phone, email, birthday, birthday_reminder
                        self.update_contact_by_user_id_and_contact_id(
                            user_id, contact["name"], contact["address"], contact["phone"], contact["email"],
                            contact["birthday"], int(contact["birthday_reminder"]), contact["id"]
                        )
                        # set the update_pending flag to false
                        contact["update_pending"] = False
                    else:
                        continue

    @insert_or_update_contacts_in_database.before_loop
    async def before_insert_or_update_contacts_in_database(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def check_birthday_notification(self):
        for user, info in self.address_book.items():
            user_tz = pytz.timezone(info["tz"])
            now = datetime.now(user_tz)
            # we really only want to alert people on the day of (relative to them)
            if 0 <= now.hour < 1:
                for contact in info["address_book"]:
                    # if the birthday exists, reminder is set to 1 i.e. true then lets check
                    if int(contact["birthday_reminder"]) and contact["birthday"] != "" and contact["birthday"] is not None:
                        # birthday is a datetime object, so we can call day/month/hour
                        bday = contact["birthday"]
                        # if the day and month match, and the year is either greater or equal, it's their birthday!!
                        if now.day == bday.day and now.month == bday.month and now.year >= bday.year:
                            # happy birthday sucka! let's make sure your friends remember you, you nameless hero
                            user = self.bot.get_user(info["disc_id"])
                            await user.create_dm()
                            await user.dm_channel.send(
                                f'It\'s {contact["name"]}\'s birthday! '
                                f'Don\'t forget to wish them a happy birthay today!'
                            )

    @check_birthday_notification.before_loop
    async def before_check_birthday_notification(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(AddressBook(bot))
