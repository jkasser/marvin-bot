from discord.ext import commands, tasks
from utils.db import SubscriptionsDB
from asyncio import TimeoutError
from utils import timezones, enums
from utils.helper import check_if_valid_hour, map_active_to_bool
from datetime import datetime
from dateutil.relativedelta import relativedelta
from cogs.weather import Weather
import pytz


class Subscriptions(commands.Cog, SubscriptionsDB):

    SUBSCRIPTION_TABLE_NAME = "subs"
    SUBSCRIPTION_TABLE = f"""CREATE TABLE IF NOT EXISTS {SUBSCRIPTION_TABLE_NAME} (
        id integer PRIMARY KEY,
        user_id integer NOT NULL,
        sub_type text NOT NULL,
        sub_details text NOT NULL,
        when_send integer NOT NULL,
        active integer NOT NULL,
        last_sent timestamp,
        FOREIGN KEY(user_id) REFERENCES {SubscriptionsDB.SUB_USERS_TABLE_NAME}(id)
    );"""
    INSERT_SUB = f"""INSERT INTO {SUBSCRIPTION_TABLE_NAME}(user_id, sub_type, sub_details, when_send, active, last_sent) 
    VALUES(?,?,?,?,?,?)"""
    CHECK_IF_SUB_EXISTS = f"""SELECT EXISTS(SELECT * FROM {SUBSCRIPTION_TABLE_NAME} 
                                WHERE user_id=? AND sub_type = ? LIMIT 1)"""
    UPDATE_SUB_LAST_SENT = f"""UPDATE {SUBSCRIPTION_TABLE_NAME} SET last_sent = ? where id = ?"""
    UPDATE_SUB_ACTIVE_STATUS = f"""UPDATE {SUBSCRIPTION_TABLE_NAME} SET active = ? where id = ?"""
    GET_ALL_SUBS = f"""SELECT * FROM {SUBSCRIPTION_TABLE_NAME} GROUP BY user_id"""
    GET_ACTIVE_SUBS_BY_USER_ID = f"""SELECT * FROM {SUBSCRIPTION_TABLE_NAME} WHERE active = 1 AND user_id = ?"""

    def __init__(self, bot):
        super(Subscriptions, self).__init__()
        self.user_subs = dict()
        self.bot = bot
        self.create_table(self.conn, self.SUBSCRIPTION_TABLE)
        # put it all into memory
        users = self.users
        if len(users) > 0:
            for user in users:
                self.user_subs[user[1]] = dict(user_id=user[0], tz=user[2], disc_id=user[3], sub_list=[])
                # retrieve the subs for this user by user ID
                subs = self.get_active_subs(user[0])
                for sub in subs:
                    sub_dict = dict(
                        id=sub[0], type=sub[2], details=sub[3], when=sub[4], active=sub[5], last_sent=sub[6]
                    )
                    self.user_subs[user[1]]["sub_list"].append(sub_dict)

        self.insert_or_update_subs_in_db.start()
        self.check_if_time_to_notify_user_of_sub.start()

    def get_subs(self):
        return self.get_query(self.GET_ALL_SUBS)

    def get_active_subs(self, user_id):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_ACTIVE_SUBS_BY_USER_ID, (user_id,))
        results = results.fetchall()
        self.conn.commit()
        return results

    def insert_sub(self, user_id, sub_type, sub_details, when_send, active, last_sent):
        return self.insert_query(self.INSERT_SUB, (user_id, sub_type, sub_details, when_send, active, last_sent,))

    def update_last_sent_time_for_sub_by_id(self, sub_id, last_sent):
        self.update_query(self.UPDATE_SUB_LAST_SENT, (last_sent, sub_id,))

    def update_sub_active_status(self, sub_id, active):
        self.update_query(self.UPDATE_SUB_ACTIVE_STATUS, (active, sub_id,))

    # keep this one here since it needs access to the bot
    def get_user_object_by_id(self, user_id):
        user = self.bot.fetch_user(user_id)
        # returns, name, id, etc
        return user

    @commands.command(name='subsettz', help='Set your timezone for your user profile!')
    async def set_subscription_timezone(self, ctx, supplied_tz=None):
        timeout = 30
        user = str(ctx.author)
        def check(m):
            return m.author.name == ctx.author.name
        if user in self.user_subs.keys() and self.user_subs[user]["tz"] != "":
            user_tz = self.user_subs[user]["tz"]
            await ctx.send(f'You have already set your timezone to: {user_tz}!\n'
                           f'If you would like to update it, please call !subupdatetz')
            return
        else:
            # add the user to our dict and add their discord ID to the body
            self.user_subs[user] = dict(disc_id=ctx.author.id)
            if supplied_tz is None:
                await ctx.send('Please enter your preferred timezone! Here are some examples:\n'
                               'America/Denver, US/Eastern, US/Alaska, Europe/Berlin')
                try:
                    user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
                    user_answer = user_answer.content
                    possible_tz = timezones.get_possible_timezones(user_answer)
                    if timezones.check_if_timezone_match(possible_tz):
                        await ctx.send(f'I have found the matching timezone: {possible_tz[0]}.\n'
                                       f'Your timezone has been set successfully!')
                    else:
                        if len(possible_tz) == 0:
                            await ctx.send(f'Your provided timezone: {user_answer}, does not match any timezones!\n'
                                           f'Please try this command again. To get a list of timezones, call !gettimezones')
                        elif len(possible_tz) > 1:
                            await ctx.send(f'I have found the following possible matches: {", ".join(possible_tz)}.\n'
                                           f'Please try this again after deciding which timezone you would like to use!')
                            # bail out since they provided an ambiguous match
                        return
                except TimeoutError:
                    await ctx.send('You have taken too long to decide! Good-bye!')
                    return
            else:
                possible_tz = timezones.get_possible_timezones(supplied_tz)
                if timezones.check_if_timezone_match(possible_tz):
                    await ctx.send(f'I have found the matching timezone: {possible_tz[0]}.\n'
                                   f'Your timezone has been set successfully!')
                else:
                    if len(possible_tz) == 0:
                        await ctx.send(f'Your provided timezone: {supplied_tz}, does not match any timezones!\n'
                                       f'Please try this command again. To get a list of timezones, call !gettimezones')
                    elif len(possible_tz) > 1:
                        await ctx.send(f'I have found the following possible matches: {", ".join(possible_tz)}.\n'
                                       f'Please try this again after deciding which timezone you would like to use!')
                        # bail out since they provided an ambiguous match
                    return

    @commands.command(name='subupdatetz', help='Change your current timezone.')
    async def update_timezone(self, ctx):
        timeout = 30
        user = str(ctx.author)
        def check(m):
            return m.author.name == ctx.author.name
        await ctx.send(f'Your current timezone is set to: {self.user_subs[user]["tz"]}\n'
                       f'Please enter your new preferred timezone! Here are some examples:\n'
                       'America/Denver, US/Eastern, US/Alaska, Europe/Berlin')
        try:
            user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
            user_answer = user_answer.content
            possible_tz = timezones.get_possible_timezones(user_answer)
            if timezones.check_if_timezone_match(possible_tz):
                await ctx.send(f'I have found the matching timezone: {possible_tz[0]}')
                if user in self.user_subs.keys():
                    # if the user exists, just set the timezone value
                    self.user_subs[user]["tz"] = possible_tz[0]
                else:
                    # else create the user and set TZ
                    self.user_subs[user] = dict(tz=possible_tz[0])
                await ctx.send('Your timezone has been set!')
            else:
                if len(possible_tz) == 0:
                    await ctx.send(f'Your provided timezone: {user_answer}, does not match any timezones!\n'
                                   f'Please try this command again. To get a list of timezones, call !gettimezones')
                elif len(possible_tz) > 1:
                    await ctx.send(f'I have found the following possible matches: {", ".join(possible_tz)}.\n'
                                   f'Please try this again after deciding which timezone you would like to use!')
                    # bail out since they provided an ambiguous match
                return
        except TimeoutError:
            await ctx.send('You have taken too long to decide! Good-bye!')
            return

    @commands.command(name='gettimezones', help='Get a list of timezones in a direct message.')
    async def send_timezones_in_dm(self, ctx):
        channel = await ctx.author.create_dm()
        tzs = ""
        for tz in timezones._timezones:
            tzs += f'{tz}, '
            if len(tzs) > 1900:
                await channel.send(tzs)
            else:
                continue

    @commands.command(name='subweather', help='This will subscribe you to weather! Just pass in your location.')
    async def subscribe_user_to_weather(self, ctx):
        timeout = 120
        user = str(ctx.author)
        sub_type = 'weather'
        def check(m):
            return m.author.name == ctx.author.name
        # user doesnt exist or they haven't set their timezone
        if user not in self.user_subs.keys() or ("tz" in self.user_subs[user].keys() and self.user_subs[user]["tz"] == ""):
            await ctx.send('You have not set your timezone! Please call !subsettz first!')
            # break out user needs to set timezone
            return
        # user exists and has set timezone
        else:
            # let's get their zip code
            await ctx.send('Where would you like to subscribe to for weather notifications?\n'
                           'E.g. Zip code like 80021, City, (State/Country) like Berlin, Germany')
            try:
                user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
                sub_details = user_answer.content
                await ctx.send(f'You have chosen to get weather alerts for {sub_details}\n'
                               f'Is this correct? Y/N')
                confirm_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
                # If the location is correct let's move on to what time they want the alert
                if confirm_answer.content.lower().strip() in ['y', 'yes']:
                    await ctx.send('What hour of the day would you like me to send you notifications?\n'
                                   'Please enter a whole number between 1 and 24.')
                    time_of_day = await self.bot.wait_for("message", check=check, timeout=timeout)
                    time_of_day = time_of_day.content
                    if check_if_valid_hour(str(time_of_day)):
                        # we have finally made it, add the sub details to the list
                        if "sub_list" not in self.user_subs[user].keys():
                            sublist = self.user_subs[user]["sub_list"] = []
                        else:
                            sublist = self.user_subs[user]["sub_list"]
                        sublist.append(
                            {
                                # leave ID blank since this is coming from memory
                                # Type, Details, When
                                "details": sub_details, # location
                                "type": sub_type, # defaults to weather for this command
                                "when": int(time_of_day),
                                "active": True,
                                # set last sent to 1 day ago to get the ball rolling (should run on the next check)
                                "last_sent": datetime.now(pytz.timezone(self.user_subs[user]["tz"])) - relativedelta(days=1)
                            }
                        )
                        await ctx.send(f'Great! '
                                       f'I have you scheduled to receive {sub_type} alerts for: {sub_details} '
                                       f'around {time_of_day}:00 every day.')
                    else:
                        await ctx.send('Your supplied value was incorrect! Please pick a number between 1 and 24 and'
                                       ' try this command again!')
                else:
                    await ctx.send('You claimed the location was not correct, please try this command again!')
                    return
            except TimeoutError:
                await ctx.send('You have taken too long to decide! Good-bye!')
                return

    @commands.command(name='subget', help='Get a list of subscriptions for your user!')
    async def return_users_subs(self, ctx):
        user = str(ctx.author)
        # we only need to get subs for the user
        try:
            for x in self.user_subs[user]["sub_list"]:
                if "id" in x.keys():
                    sub_type = x["type"]
                    sub_hour = x["when"]
                    sub_details = x["details"]
                    last_sent = x["last_sent"]
                    sub_active = x["active"]
                    sub_id = x["id"]
                    if sub_active == 0:
                        active_status = 'inactive'
                    else:
                        active_status = 'active'
                    await ctx.send(
                        f'You have an **{active_status}** **{sub_type}** sub for **{sub_details}** at **{sub_hour}:00**.\n'
                        f'This sub was last sent at: {last_sent} and it\'s id is **{sub_id}**.'
                    )
            temporary_subs = [x for x in self.user_subs[user]["sub_list"] if "id" not in x.keys()]
            if len(temporary_subs) > 0:
                await ctx.send(f'You have {len(temporary_subs)} still pending in memory! Please check back in 5 minutes!')
        except KeyError:
            await ctx.send('You have no current subscriptions! Set your timezone with !subsettz then try !subweather.')

    @commands.command(name='subupdate', help='Update a sub by it\'s ID, and either active or inactive.')
    async def update_sub_for_user(self, ctx, sub_id, active):
        sub_id = int(sub_id)
        user = str(ctx.author)
        # check if the id even exists first
        if sub_id in [sub["id"] for sub in self.user_subs[user]["sub_list"]]:
            # if it does, then access it directly
            for sub in self.user_subs[user]["sub_list"]:
                if sub["id"] == sub_id:
                    # if an id is there (its been inserted) and the provided id matches
                    if "id" in sub.keys() and sub_id == sub["id"]:
                        try:
                            # set it equal to the preferred activeness
                            sub["active"] = map_active_to_bool(str(active).lower())
                            # now update the database
                            self.update_sub_active_status(sub_id, sub["active"])
                            await ctx.send(f'Your sub {sub["id"]} has been set to {active}!')
                            return
                        except KeyError:
                            # This means they didn't provide active/inactive correctly!
                            await ctx.send(f'You said set it to {active}. '
                                           f'My only possible choices are: {",".join(enums.ACTIVE_ENUM.keys())}')
                            return
                else:
                    continue
        else:
            await ctx.send(f'I cannot find a sub by id: {sub_id}. Please try again!')
            return

    @tasks.loop(minutes=5)
    async def insert_or_update_subs_in_db(self):
        # do some stuff here to insert
        for user, info in self.user_subs.items():
            # if we haven't set the user ID, then we haven't stored it yet
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
            # if sub_list isnt in info.keys then the user has just set their tz, not created any subscriptions yet
            if "sub_list" in info.keys():
                # now get every sub id in the database that is active, check if id in sub_ids
                for sub in info["sub_list"]:
                    if "id" not in sub.keys():
                        # then we know we have to insert into the database
                        sub_id = self.insert_sub(user_id, sub["type"], sub["details"], sub["when"], sub["active"], sub["last_sent"])
                        # set the sub ID in the dict
                        sub["id"] = sub_id
                    else:
                        continue

    @insert_or_update_subs_in_db.before_loop
    async def before_insert_or_update_subs_in_db(self):
      await self.bot.wait_until_ready()

    @tasks.loop(minutes=15)
    async def check_if_time_to_notify_user_of_sub(self):
        for user, info in self.user_subs.items():
            user_tz = pytz.timezone(info["tz"])
            now = datetime.now(user_tz)
            for sub in info["sub_list"]:
                # if the sub is active
                if sub["active"] and "id" in sub.keys():
                    sub_type = sub["type"]
                    sub_hour = sub["when"]
                    sub_details = sub["details"]
                    last_sent = sub["last_sent"]
                    if isinstance(last_sent, datetime):
                        # compare now vs last_sent with timezone
                        if now.month > last_sent.month or now.day > last_sent.day:
                            # compare the hours
                            if now.hour >= int(sub_hour):
                                # create the dm channel
                                user = self.bot.get_user(info["disc_id"])
                                await user.create_dm()
                                # it's time to send this bad boy!
                                # call some logic here to run the sub
                                if sub_type.lower() == 'weather':
                                    # invoke the bot get weather command
                                    weather_embed = Weather(self.bot).get_weather_for_area(sub_details)
                                    await user.dm_channel.send(embed=weather_embed)
                                    # update the last sent time in memory and in the database
                                    sub["last_sent"] = datetime.now(user_tz)
                                    self.update_last_sent_time_for_sub_by_id(sub["id"], datetime.now(user_tz))
                        else:
                            continue

    @check_if_time_to_notify_user_of_sub.before_loop
    async def before_check_if_time_to_notify_user_of_sub(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Subscriptions(bot))
