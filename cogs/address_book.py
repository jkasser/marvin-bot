from discord.ext import commands, tasks
from utils.db import MarvinDB
from bson import ObjectId
from asyncio import TimeoutError
from utils.helper import (
    decode_value,
    encode_value,
    parse_string_to_datetime,
    turn_datetime_into_string
)
from utils import timezones
from datetime import datetime
import pytz


class AddressBook(commands.Cog, MarvinDB):

    USERS_TABLE_NAME = "users"
    ADDRESS_TABLE_NAME = "contacts"

    # users table fields
    USERNAME = "username"
    DATE_OF_BIRTH = "dob"  # shared with contact book
    TIMEZONE = "timezone"
    DISCORD_ID = "disc_id"  # shared with contact book

    # contact book
    NAME = "name"
    PHONE = "phone"
    ADDRESS = "address"
    EMAIL = "email"
    SHARE_WITH = "share_with"  # list

    ENCODED_FIELDS = [
        PHONE,
        ADDRESS,
        NAME,
        EMAIL
    ]

    # name of contacts list where all contacts will exist for a given user
    CONTACTS = "contacts"

    def __init__(self, bot):
        super(AddressBook, self).__init__()
        self.address_book = {}
        self.bot = bot
        # create the address table if it doesn't exist
        self.users_table = self.select_collection(self.USERS_TABLE_NAME)
        self.contacts_table = self.select_collection(self.ADDRESS_TABLE_NAME)
        # get all our users
        users = self.run_find_many_query(
            self.users_table,
            {},
        )
        if len(users) > 0:
            for user in users:
                self.address_book[user[self.USERNAME]] = {
                    "_id": user["_id"],
                    self.DISCORD_ID: user[self.DISCORD_ID],
                    self.TIMEZONE: user[self.TIMEZONE],
                    self.DATE_OF_BIRTH: None,
                    self.CONTACTS: []
                }
                addresses = self._get_address_book_for_user(user[self.DISCORD_ID])
                for address in addresses:
                    # the info will be stored encoded
                    contact_info = {
                        "_id": address["_id"],
                        self.DISCORD_ID: user[self.DISCORD_ID],
                        self.NAME: decode_value(address[self.NAME]),
                        self.PHONE: decode_value(address[self.PHONE]),
                        self.ADDRESS: decode_value(address[self.ADDRESS]),
                        self.DATE_OF_BIRTH: address[self.DATE_OF_BIRTH],
                        self.EMAIL: decode_value(address[self.EMAIL]),
                        self.SHARE_WITH: address[self.SHARE_WITH],
                    }
                    self.address_book[user[self.USERNAME]][self.CONTACTS].append(contact_info)
        self.check_birthday_notification.start()
        self.insert_or_update_contacts_in_database.start()

    def _get_address_book_for_user(self, user_discord_id):
        results = self.run_find_many_query(
            self.contacts_table,
            {
                self.DISCORD_ID: user_discord_id
            }
        )
        if results is None:
            results = []
        return results

    def _insert_contact_into_db(
        self, user_discord_id, name, address, phone, email, date_of_birth, shared_with,
    ):
        contact_id = self.contacts_table.insert_one(
            {
                self.DISCORD_ID: user_discord_id,
                self.NAME: encode_value(name),
                self.ADDRESS: encode_value(address),
                self.PHONE: encode_value(phone),
                self.DATE_OF_BIRTH: {"$date": date_of_birth},
                self.EMAIL: encode_value(email),
                self.SHARE_WITH: shared_with
            }
        )
        return contact_id.inserted_id

    def _update_contact_by_contact_id(
        self,
        contact_id,
        updated_payload: dict,
    ):
        # encode it before inserting if we need to
        for k, v in updated_payload.items():
            if k in self.ENCODED_FIELDS:
                updated_payload[k] = encode_value(v)
        return self.set_field_for_object_in_table(
            table=self.contacts_table,
            record_id_to_update=contact_id,
            query_to_run=updated_payload,
        )

    def _delete_contact_by_id(self, contact_id):
        return self.contacts_table.delete_one(
            {
                "_id": ObjectId(contact_id),
            }
        )

    @commands.command(
        name="contactlist", aliases=["listcontacts"], help="List all of your contacts!"
    )
    async def list_all_contact_names(self, ctx):
        user = str(ctx.author)
        if user in self.address_book.keys():
            channel = await ctx.author.create_dm()
            contacts = sorted(
                [contact for contact in self.address_book[user][self.CONTACTS]],
                key=lambda k: k["name"],
            )
            if len(contacts) > 0:
                msg = ""
                for x in contacts:
                    msg += f'{x["name"].title()}\n'
                await channel.send(msg)
            else:
                # we can't find anyone
                await ctx.send(f"You have no contacts with me!")
        else:
            await ctx.send(
                "Before you can use my address book feature, I need to get your timezone "
                '(for reminders)! Please type "!subsettz" to set your timezone with me, and then try '
                'adding a contact with "!contactadd".'
            )

    @commands.command(
        name="getcontact",
        aliases=["searchcontact", "searchcontacts", "contactsearch", "contactget"],
        help="Search for a contact in your address book! I will return all matching results.",
    )
    async def get_contact_by_name(self, ctx, *contact_name):
        timeout = 60
        user = str(ctx.author)
        contact_name = " ".join(contact_name)

        def check(m):
            return m.author.name == ctx.author.name

        if contact_name == "":
            await ctx.send("Please provide a name for the new contact!")
            try:
                contact_name = await self.bot.wait_for(
                    "message", check=check, timeout=timeout
                )
                contact_name = contact_name.content
                if contact_name.lower() == "cancel":
                    await ctx.send("This command has been cancelled! Goodbye.")
                    return
            except TimeoutError:
                await ctx.send("Error: Please try again with !contactadd <name>")
                return
        await ctx.send(f"Looking up {contact_name.title()}...")
        if user in self.address_book.keys():
            channel = await ctx.author.create_dm()
            potential_hits = [
                contact
                for contact in self.address_book[user][self.CONTACTS]
                if contact_name.lower() in contact[self.NAME].lower()
            ]
            if len(potential_hits) > 0:
                await ctx.send(
                    f"I have found {len(potential_hits)} matche(s) and "
                    f"will send the relevant info to you via a direct message!"
                )
                for hit in potential_hits:
                    msg = f'**{hit["name"].title()}\'s Information:**\n'
                    for field, value in hit.items():
                        if field.lower() == self.DATE_OF_BIRTH and value is None:
                            value = ""
                        msg += f"{str(field)}: {str(value).title()}\n"
                    # add a blank line between entries
                    msg += "\n\n"
                    await channel.send(msg)
            else:
                # we can't find anyone
                await ctx.send(
                    f"Sorry! I was unable to find a contact by the name of {contact_name}."
                )
        else:
            await ctx.send(
                "Before you can use my address book feature, I need to get your timezone "
                '(for reminders)! Please type "!subsettz" to set your timezone with me, and then try '
                'adding a contact with "!contactadd".'
            )

    @commands.command(name='subsettz', aliases=['settz', 'timezone', 'tz'],
                      help='Set your timezone for your user profile!')
    async def set_subscription_timezone(self, ctx, supplied_tz=None):
        timeout = 30
        user = str(ctx.author)

        def check(m):
            return m.author.name == ctx.author.name

        user_tz = self.address_book[user][self.TIMEZONE]
        if user in self.address_book.keys() and user_tz is not None:
            await ctx.send(f'You have already set your timezone to: {user_tz}!\n'
                           f'If you would like to update it, please call !subupdatetz')
            return
        else:
            if supplied_tz is None:
                await ctx.send('Please enter your preferred timezone! Here are some examples:\n'
                               'America/Denver, US/Eastern, US/Alaska, Europe/Berlin')
                try:
                    user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
                    user_answer = user_answer.content
                    possible_tz = timezones._get_possible_timezones(user_answer)
                    if timezones._check_if_timezone_match(possible_tz):
                        await ctx.send(f'I have found the matching timezone: {possible_tz[0]}.\n'
                                       f'Your timezone has been set successfully!')
                        # add the user to our dict and add their discord ID to the body
                        user_sub = {
                            self.USERNAME: user,
                            self.DISCORD_ID: ctx.author.id,
                            self.TIMEZONE: None,
                            self.DATE_OF_BIRTH: None,
                        }
                        # insert the user
                        user_id = self.users_table.insert_one(
                            user_sub
                        ).inserted_id
                        self.address_book[user] = {"_id": user_id}
                        # merge them
                        self.address_book[user] = self.address_book[user] | user_sub
                    else:
                        if len(possible_tz) == 0:
                            await ctx.send(f'Your provided timezone: {user_answer}, does not match any timezones!\n'
                                           f'Please try this command again. To get a list of timezones, '
                                           f'call !gettimezones')
                        elif len(possible_tz) > 1:
                            await ctx.send(f'I have found the following possible matches: {", ".join(possible_tz)}.\n'
                                           f'Please try this again after deciding which timezone you would like '
                                           f'to use!')
                            # bail out since they provided an ambiguous match
                        return
                except TimeoutError:
                    await ctx.send('You have taken too long to decide! Good-bye!')
                    return
            else:
                possible_tz = timezones._get_possible_timezones(supplied_tz)
                if timezones._check_if_timezone_match(possible_tz):
                    await ctx.send(f'I have found the matching timezone: {possible_tz[0]}.\n'
                                   f'Your timezone has been set successfully!')
                    # add the user to our dict and add their discord ID to the body
                    user_sub = {
                        self.USERNAME: user,
                        self.DISCORD_ID: ctx.author.id,
                        self.TIMEZONE: None,
                        self.DATE_OF_BIRTH: None,
                    }
                    # insert the user
                    user_id = self.users_table.insert_one(
                        user_sub
                    ).inserted_id
                    self.address_book[user] = {"_id": user_id}
                    # merge them
                    self.address_book[user] = self.address_book[user] | user_sub
                else:
                    if len(possible_tz) == 0:
                        await ctx.send(f'Your provided timezone: {supplied_tz}, does not match any timezones!\n'
                                       f'Please try this command again. To get a list of timezones, call !gettimezones')
                    elif len(possible_tz) > 1:
                        await ctx.send(f'I have found the following possible matches: {", ".join(possible_tz)}.\n'
                                       f'Please try this again after deciding which timezone you would like to use!')
                        # bail out since they provided an ambiguous match
                    return

    def retrieve_contacts_number(self, user, contact_name):
        results = {
            "contact_found": False,
            "contact_number": None,
            "error_msg": "",
            "potential_contacts": [],
        }
        if user in self.address_book.keys():
            potential_hits = [
                contact
                for contact in self.address_book[user][self.CONTACTS]
                if contact_name.lower() == contact[self.NAME].split()[0].lower()
            ]
            if len(potential_hits) == 1:
                results["contact_found"] = True
                results[self.PHONE] = potential_hits[0][self.PHONE]
            elif len(potential_hits) > 1:
                new_line = "\n"
                enumerated_contact_list = f'{new_line.join([str(result) for result in results["potential_contacts"]])}'
                results["contact_found"] = True
                results["potential_contacts"] = [
                    (hit[self.NAME], hit[self.PHONE]) for hit in potential_hits
                ]
                results["error_msg"] = (
                    "We have found multiple contacts! Which contact would you like to use? Provide"
                    f" the number of the contact below. {enumerated_contact_list}"
                )
            else:
                # we can't find anyone, or found too many results
                results[
                    "error_msg"
                ] = f"Sorry! I was unable to find a contact by the name of {contact_name}."
        else:
            results["error_msg"] = (
                "Before you can use my address book feature, I need to get your timezone "
                '(for reminders)! Please type "!subsettz" to set your timezone with me, and then '
                'try adding a contact with "!contactadd".'
            )
        return results

    @commands.command(
        name="contactadd",
        aliases=["addcontact"],
        help="Add an entry to your address book!",
    )
    async def add_contact(self, ctx, *contact_name):
        timeout = 60
        user = str(ctx.author)
        contact_name = " ".join(contact_name)

        def check(m):
            return m.author.name == ctx.author.name

        if user in self.address_book.keys():
            if contact_name == "":
                await ctx.send("Please provide a name for the new contact!")
                try:
                    contact_name = await self.bot.wait_for(
                        "message", check=check, timeout=timeout
                    )
                    contact_name = contact_name.content
                except TimeoutError:
                    await ctx.send("Error: Please try again with !contactadd <name>")
                    return
            try:
                # it's possible a user does this right after sub set tz
                # at which point we won't have this list available
                if self.CONTACTS not in self.address_book[user].keys():
                    # create this in memory
                    self.address_book[user][self.CONTACTS] = []
                else:
                    # If an address book is present, see if the contact already exists
                    potential_hits = [
                        contact
                        for contact in self.address_book[user][self.CONTACTS]
                        if contact_name.lower() in contact[self.NAME].lower()
                    ]
                    if len(potential_hits) > 0:
                        await ctx.send(
                            f"I have found {len(potential_hits)} possible matche(s) "
                            f"already in your contacts. Are you sure this is a new contact? Y/N"
                        )
                        confirm_name = await self.bot.wait_for(
                            "message", check=check, timeout=timeout
                        )
                        # if the name is correct then let's create an entry
                        if confirm_name.content.lower().strip() not in ["y", "yes"]:
                            await ctx.send(
                                "No problem, you can always search for a contact with "
                                "!getcontact to be sure. Just call !contactadd whenever you are "
                                "ready to try again!"
                            )
                            # bail out
                            return
                # store the address book as a variable to make it easier to work with
                contact_info = self.address_book[user][self.CONTACTS]
                # check if the name provided is correct
                await ctx.send(
                    f"Ok! Let's add {contact_name.title()} to your address book!"
                    f"\nIs the name correct? Y/N"
                )
                confirm_name = await self.bot.wait_for(
                    "message", check=check, timeout=timeout
                )
                # if the name is correct then let's create an entry
                if confirm_name.content.lower().strip() in ["y", "yes"]:
                    await ctx.send(
                        "Great! I will now gather info about your contact. If you don't have "
                        "or don't wish to provide the requested info (it will be hashed when stored),"
                        ' just reply "skip".\nI will now DM you for the following information in order'
                        " to preserve your privacy."
                    )
                    channel = await ctx.author.create_dm()
                    await channel.send(
                        "Could you please provide the address? If you wish to skip "
                        'any of the fields, just reply with "skip".'
                    )
                    addr_response = await self.bot.wait_for(
                        "message", check=check, timeout=timeout
                    )
                    addr_response = addr_response.content
                    # if they choose to skip we just need to store a blank string
                    if addr_response.lower().strip() == "skip":
                        addr_response = ""
                        await channel.send("Skipping address!")
                    # phone
                    await channel.send("Contact's phone number?")
                    phone_response = await self.bot.wait_for(
                        "message", check=check, timeout=timeout
                    )
                    phone_response = phone_response.content
                    if phone_response.lower().strip() == "skip":
                        phone_response = ""
                        await channel.send("Skipping phone!")
                    # email
                    await channel.send("Contact's email?")
                    email_response = await self.bot.wait_for(
                        "message", check=check, timeout=timeout
                    )
                    email_response = email_response.content
                    if email_response.lower().strip() == "skip":
                        email_response = ""
                        await channel.send("Skipping email!")
                    # birthday
                    await channel.send(
                        "Contact's birthday? (MM/DD/YYYY)\nIf year isn't provided I will default "
                        "to the current year"
                    )
                    bday_response = await self.bot.wait_for(
                        "message", check=check, timeout=timeout
                    )
                    bday_response = bday_response.content
                    if bday_response.lower().strip() == "skip":
                        bday_response = None
                        await channel.send("Skipping birthday!")
                    else:
                        try:
                            bday_response = parse_string_to_datetime(bday_response)
                        except Exception:
                            bday_response = ""
                            await channel.send(
                                "I was unable to parse your provided birthday,"
                                " I will continue but leave it blank."
                            )
                    # OK FINALLY create the entry in the book
                    contact_dict = {
                        self.NAME: contact_name.title(),
                        self.ADDRESS: addr_response,
                        self.PHONE: phone_response,
                        self.EMAIL: email_response,
                        self.DATE_OF_BIRTH: bday_response,
                        self.SHARE_WITH: [],
                    }
                    # now append it! we are done!
                    contact_info.append(contact_dict)
                    await channel.send(
                        f"I have successfully added "
                        f"{contact_name.title()} to your address book!"
                    )
                    return
                else:
                    # if it's incorrect then bail out
                    await ctx.send(
                        'Ok! Just call "!contactadd" when you are ready to try again! Good-bye!'
                    )
                    return
            except TimeoutError:
                await ctx.send("You took too long to reply! Please try again!")
        else:
            await ctx.send(
                "Before you can use my address book feature, I need to get your timezone (for reminders)! "
                'Please type "!subsettz" to set your timezone with me, and then try adding a contact with'
                '"!contactadd".'
            )

    @commands.command(
        name="contactdelete",
        aliases=["deletecontact", "delcontact"],
        help="Remove a contact by their name.",
    )
    async def delete_contact(self, ctx, contact_id=None):
        user = str(ctx.author)
        if contact_id is None:
            await ctx.send(
                "You must supply an ID of the contact to delete! If you don't see an ID yet then give it "
                "a few minutes while I update my database! Once an ID is present you can update the "
                "applicable contact."
            )
            return
        if user in self.address_book.keys():
            # check if they have any contacts
            if len(self.address_book[user][self.CONTACTS]) == 0:
                await ctx.send("You have no contacts! Add some with !contactadd.")
                return
            else:
                # if they have contacts let's get the contact - do a str compare on ID since it could be an empty string
                contact = [
                    contact
                    for contact in self.address_book[user][self.CONTACTS]
                    if contact["_id"] == contact_id
                    if "_id" in contact.keys()
                ]
                if len(contact) == 0:
                    await ctx.send(
                        f"I wasn't able to find a contact that matched ID: {contact_id}. It takes me a couple"
                        f" minutes to update my database which is where I get the ID from. You can always "
                        f"do a !contactget <contact name> to see if that contact exists and what their ID "
                        f"is!"
                    )
                    return
                elif len(contact) > 1:
                    await ctx.send(
                        f"Somehow I have found {len(contact)} matches. Please contact an admin."
                    )
                    return
                else:
                    contact = contact[0]
                    await ctx.send(f'Deleting entry for {contact[self.NAME]}!')
                    del self.address_book[user][self.CONTACTS][
                        self.address_book[user][self.CONTACTS].index(contact)
                    ]
                    # now delete from the database as well
                    self._delete_contact_by_id(contact_id)
                    await ctx.send("Contact deleted!")

    @commands.command(
        name="contactupdate",
        aliases=["updatecontact"],
        help="Update a contact by their name.",
    )
    async def update_contact(self, ctx, contact_id=None, field=None, *value):
        user = str(ctx.author)
        try:
            value = " ".join(value)
        except Exception as e:
            await ctx.send(
                f"Error: You must supply the new value that I should update {field} to! Please try again"
                f" with !contactupdate <contactID> <field> <value>.\n{e}"
            )
            return
        if contact_id is None:
            await ctx.send(
                "You must supply an ID of the contact to update! If you don't see an ID yet then give it "
                "a few minutes while I update my database! Once an ID present you can update the "
                "applicable contact. The ID must be an integer!"
            )
            return
        elif field is None:
            await ctx.send(
                "You must supply the field you wish to update, e.g. name/phone/address/email/birthday"
            )
            return
        elif value is None:
            await ctx.send(
                f"You must supply the new value that I should update {field} to!"
            )
            return
        elif field.lower() == "_id":
            await ctx.send("You cannot update the ID of a record!")
            return
        elif field.lower() in self.DATE_OF_BIRTH:
            try:
                potential_bday = parse_string_to_datetime(value)
            except Exception:
                potential_bday = None
            if not isinstance(potential_bday, datetime):
                await ctx.send(
                    f"The format of {value} was not correct."
                    f" Please supply a birthday in the format of MM/DD/YYYY."
                )
                return
        # ok check if the user exists
        if user in self.address_book.keys():
            # check if they have any contacts
            if len(self.address_book[user][self.CONTACTS]) == 0:
                await ctx.send("You have no contacts! Add some with ```!contactad <name>```.")
                return
            else:
                # if they have contacts let's get the contact - do a str compare on ID since it could be an empty string
                contact = [
                    contact
                    for contact in self.address_book[user][self.CONTACTS]
                    if contact["_id"] == contact_id
                    if "_id" in contact.keys()
                ]
                if len(contact) == 0:
                    await ctx.send(
                        f"I wasn't able to find a contact that matched ID: {contact_id}. It takes me a "
                        f"couple minutes to update my database which is where I get the ID from. "
                        f"You can always do a !contactget <contact name> to see if that contact exists "
                        f"and what their ID is!"
                    )
                    return
                elif len(contact) > 1:
                    await ctx.send(
                        f"Somehow I have found {len(contact)} matches. Please contact an admin."
                    )
                    return
                else:
                    contact = contact[0]

                    if field.lower() == self.DATE_OF_BIRTH:
                        str_value = value
                        value = parse_string_to_datetime(value)
                    else:
                        str_value = value
                    if field.lower() in contact.keys():
                        contact[field.lower()] = value
                        # now we also want to set the update flag to True here
                        contact["update_pending"] = True
                        await ctx.send(
                            f"Great! I have updated the {field} to {str_value}."
                        )
                        return
                    else:
                        await ctx.send(
                            f"I could't find a valid field for: {field}. Here are the fields I have "
                            f"available to update: "
                            f'{", ".join([key for key in contact.keys() if key != "id" if key != "update_pending"])}'
                        )
                        return
        else:
            await ctx.send(
                "It looks like this is your first time using my address book feature! Please call"
                "!subsettz to set your timezone. Then you will want to add contacts before you have"
                "something to update."
            )

    @tasks.loop(minutes=3)
    async def insert_or_update_contacts_in_database(self):
        for username, info in self.address_book.items():
            if "_id" not in info.keys():
                # if the user isn't in the database we need to add him first with TZ info and get his user_id for the
                # insert the user and the timezone
                user_id = self.users_table.insert_one(
                    {
                        self.USERNAME: username,
                        self.DISCORD_ID: info[self.DISCORD_ID],
                        self.TIMEZONE: info[self.TIMEZONE],
                        self.DATE_OF_BIRTH: info[self.DATE_OF_BIRTH],
                    }
                ).inserted_id
                # add this key to the dict in memory now
                info["_id"] = user_id
            else:
                # their id is stored in memory so we can just grab the user id from there
                user_id = info["_id"]
            # if address_book isnt in info.keys then the user has just set their tz, not created any subscriptions yet
            if self.CONTACTS in info.keys():
                # now get every contact in the database
                for contact in info[self.CONTACTS]:
                    if "_id" not in contact.keys():
                        # then we know we have to insert into the database
                        # encoding happens within the insert contact method, so leave them as strings here
                        if self.SHARE_WITH not in contact.keys():
                            contact[self.SHARE_WITH] = []
                        contact_id = self._insert_contact_into_db(
                            user_id,
                            contact[self.NAME],
                            contact[self.ADDRESS],
                            contact[self.PHONE],
                            contact[self.EMAIL],
                            contact[self.DATE_OF_BIRTH],
                            contact[self.SHARE_WITH],
                        ).inserted_id
                        # set the contact ID in the dict <- from this point on users can update/delete contacts
                        contact["_id"] = contact_id
                    elif (
                        "update_pending" in contact.keys() and contact["update_pending"]
                    ):
                        # if id is in keys then lets try to update the contact
                        # expects: user_id, name, address, phone, email, birthday, birthday_reminder
                        self._update_contact_by_contact_id(
                            contact["_id"],
                            {
                                self.DISCORD_ID: info[self.DISCORD_ID],
                                self.NAME: contact[self.NAME].title(),
                                self.ADDRESS: contact[self.ADDRESS],
                                self.PHONE: contact[self.PHONE],
                                self.EMAIL: contact[self.EMAIL],
                                self.DATE_OF_BIRTH: contact[self.DATE_OF_BIRTH],
                                self.SHARE_WITH: contact[self.SHARE_WITH],
                            }
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
            user_tz = pytz.timezone(info[self.TIMEZONE])
            now = datetime.now(user_tz)
            # we really only want to alert people on the day of (relative to them)
            if 0 <= now.hour < 1:
                for contact in info[self.CONTACTS]:
                    # if the birthday exists, reminder is set to 1 i.e. true then lets check
                    if (
                        contact[self.DATE_OF_BIRTH] != ""
                        and contact[self.DATE_OF_BIRTH] is not None
                    ):
                        # birthday is a datetime object, so we can call day/month/hour
                        bday = contact[self.DATE_OF_BIRTH]
                        # if the day and month match, and the year is either greater or equal, it's their birthday!!
                        if (
                            now.day == bday.day
                            and now.month == bday.month
                            and now.year >= bday.year
                        ):
                            # happy birthday! let's make sure your friends remember you, you nameless hero
                            user = self.bot.get_user(info[self.DISCORD_ID])
                            await user.create_dm()
                            await user.dm_channel.send(
                                f'It\'s {contact[self.NAME].title()}\'s birthday! '
                                f"Don't forget to wish them a happy birthay today!"
                            )

    @check_birthday_notification.before_loop
    async def before_check_birthday_notification(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AddressBook(bot))
