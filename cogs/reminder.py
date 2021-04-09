import datetime
from asyncio import TimeoutError
from sqlite3 import Error
from discord.ext import commands, tasks
from dateutil.relativedelta import relativedelta
from dateutil import parser
from utils.enums import STR_TO_INT, TIME_IN_MINUTES, ACTIVE_ENUM
from utils.db import MarvinDB


class ReminderBot(MarvinDB, commands.Cog):

    TABLE_NAME = 'reminders'

    REMINDERS_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        user_id integer NOT NULL,
        name text NOT NULL,
        when_remind timestamp NOT NULL,
        what text NOT NULL,
        channel_id integer NOT NULL,
        active integer NOT NULL,
        repeat integer NOT NULL,
        frequency integer,
        last_sent timestamp
    );"""

    INSERT_REMINDER = f"""INSERT INTO {TABLE_NAME}(user_id,name,when_remind,what,channel_id,active,repeat,frequency,
last_sent) VALUES(?,?,?,?,?,?,?,?,?)"""
    MARK_REMINDER_INACTIVE = f"""UPDATE {TABLE_NAME} SET active = 0 WHERE id = ?"""
    UPDATE_REMINDER_LAST_SENT = f"""UPDATE {TABLE_NAME} SET last_sent = ? where id = ?"""
    GET_ACTIVE_REMINDERS = f"""SELECT * FROM {TABLE_NAME} WHERE active = 1"""
    GET_ALL_REMINDERS = f"""SELECT * FROM {TABLE_NAME} GROUP BY user_id"""
    DELETE_INACTIVE_REMINDERS = f"""DELETE FROM {TABLE_NAME} WHERE active = 0"""

    # constants
    TIME_UNITS = [
        'hours', 'days', 'minutes', 'seconds', 'weeks', 'months', 'years',
    ]


    def __init__(self, bot):
        self.bot = bot
        # if not os.path.exists('./marvin.db'):
        super().__init__()
        try:
            self.create_table(self.conn, self.REMINDERS_TABLE)
            self.reminder_dict = {}
            reminders = self._get_active_reminders()
            self._load_reminders_into_mem(reminders)
        except Error as e:
            print(e)
        self.check_for_reminders.start()
        self.delete_inactive_reminders.start()

    def _insert_reminder(self, values):
        return self.insert_query(self.INSERT_REMINDER, values)

    def _mark_reminder_inactive(self, reminder_id):
        self.update_query(self.MARK_REMINDER_INACTIVE, (reminder_id,))

    def _update_last_sent_time_for_reminder_by_id(self, sub_id, last_sent):
        self.update_query(self.UPDATE_REMINDER_LAST_SENT, (last_sent, sub_id,))

    def _get_all_reminders(self):
        return self.get_query(self.GET_ALL_REMINDERS)

    def _delete_reminders(self):
        cur = self.conn.cursor()
        cur.execute(self.DELETE_INACTIVE_REMINDERS)
        self.conn.commit()

    def _get_active_reminders(self):
        """ Returns an array of:
        0 id,
        1 name,
        2 user_id,
        3 when_remind,
        4 what,
        5 channel_id,
        6 active,
        7 repeat,
        8 frequency_minutes,
        9 last_sent """

        cur = self.conn.cursor()
        results = cur.execute(self.GET_ACTIVE_REMINDERS)
        results = results.fetchall()
        self.conn.commit()
        return results

    def _get_when_remind_date(self, date_string, start_time):
        if 'day' in date_string.lower():
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(days=delta)
        elif 'week' in date_string.lower():
            delta = float(date_string.split()[0].rstrip())
            when_remind = start_time + datetime.timedelta(weeks=delta)
        elif 'month' in date_string.lower():
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(months=+delta)
        elif 'minute' in date_string.lower():
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(minutes=delta)
        elif 'second' in date_string.lower():
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(seconds=delta)
        elif 'hour' in date_string.lower():
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(hours=delta)
        elif 'year' in date_string.lower():
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(years=+delta)
        elif 'tomorrow' in date_string.lower():
            when_remind = start_time + datetime.timedelta(days=1)
        elif 'now' in date_string.lower():
            when_remind = start_time
        else:
            when_remind = parser.parse(date_string)
        return when_remind

    def _convert_num_to_string(self, num):
        if num.lower() in STR_TO_INT.keys():
            if str:
                return str(STR_TO_INT.get(num.lower()))
            else:
                return int(STR_TO_INT.get(num.lower()))
        else:
            return num

    def _load_reminders_into_mem(self, results: list):
        for x in results:
            if x[1] not in self.reminder_dict.keys():
                # set the user id as the parent key
                self.reminder_dict[x[1]] = [{
                    "id": x[0],
                    "name": x[2],
                    "when": x[3],
                    "what": x[4],
                    "channel": x[5],
                    "active": x[6],
                    "repeat": x[7],
                    "frequency": x[8],
                    "last_sent": x[9]
                }]
            else:
                # if the user key exists, just append the reminder
                self.reminder_dict[x[1]].append({
                    "id": x[0],
                    "name": x[2],
                    "when": x[3],
                    "what": x[4],
                    "channel": x[5],
                    "active": x[6],
                    "repeat": x[7],
                    "frequency": x[8],
                    "last_sent": x[9]
                })


    @commands.command(name='remind',  aliases=['rem', 'setreminder', 'createreminder'],
                 help='Let me remind you of something! call !remind and let me guide you through setting one up!')
    async def create_reminder(self, ctx):
        timeout = 60
        now = datetime.datetime.now()
        active = 1
        author_id = ctx.author.id
        channel_id = ctx.message.channel.id
        # if the author hasn't created any reminders, add them to memory
        if author_id not in self.reminder_dict.keys():
            self.reminder_dict[author_id] = []

        def check(m):
            return m.author.name == ctx.author.name
        try:
            await ctx.send('Who would you like to remind?')
            name = await self.bot.wait_for("message", check=check, timeout=timeout)
            if name.content.lower() == 'me':
                name = ctx.author.mention
            else:
                name = name.content

            await ctx.send('What would you like me to remind you of?')
            # get the reminder text they want here
            what = await self.bot.wait_for("message", check=check, timeout=timeout)
            what = what.content
            if len(what.split()) == 0:
                await ctx.send('Please try this command again and provide me with something to remind you of!')
                return

            #move on to the next step - figure out if this is a repeat reminder or not?
            await ctx.send('Is this a repeat reminder? Y/N?')
            repeat_check = await self.bot.wait_for("message", check=check, timeout=timeout)
            repeat_check = repeat_check.content
            if 'y' == str(repeat_check).strip().lower() or 'yes' == str(repeat_check).strip().lower():
                repeat = 1

                # If it's a reminder that needs repeating, get the frequency and convert it to minutes
                await ctx.send('Great! How often would you like to repeat this reminder? Please include the unit of'
                               'time, e.g. 1 month, 2 weeks, 4 hours.')
                frequency = await self.bot.wait_for("message", check=check, timeout=timeout)
                frequency = frequency.content
                try:
                    frequency, unit = frequency.split()
                    # make sure they provided a unit we support
                    if any([unit in x for x in self.TIME_UNITS]):
                        for k,v in TIME_IN_MINUTES.items():
                            if k in unit.lower():
                                frequency = self._convert_num_to_string(frequency)
                                frequency = int(frequency) * v
                    # if we didn't find it in our list of units, tell the user
                    else:
                        await ctx.send(f'I was unable to find your provided measurement of time: {unit}. I accept'
                                       f': {", ".join(self.TIME_UNITS)}. Please try calling this command again! '
                                       f'Goodbye.')
                        return
                except ValueError:
                    await ctx.send(f'I ran into an issue processing your request. I was unable to parse {frequency} '
                                   f'Please try calling this command again and provide a frequency as well as a unit!')
                    return

            # if repeat was false, then we don't need to collect frequency
            else:
                repeat = 0
                frequency = 0
            last_sent = datetime.datetime.min
            # Alright! if we have made it this far then we have a valid frequency and unit, and have calculated the
            # appropriate time in minutes as an int for the database, as well as weather this repeats
            # Now we move on to actually getting when they want to be reminded
            await ctx.send('In how long would you like to be reminded? If this is a repeat reminder, '
                           'this will be the time from which I calculate all subsequent reminders. '
                           '\nE.g. 2 days, 4 hours, September 25, now')
            # wait for the user to reply
            start_reminder = await self.bot.wait_for("message", check=check, timeout=timeout)
            start_reminder = start_reminder.content
            try:
                when_datetime = self._get_when_remind_date(start_reminder, start_time=now)
            except ValueError:
                await ctx.send(f'I was unable to parse your provided value of: {start_reminder.content}. Please'
                               f' try this command again. Goodbye.')
                return

            # ok insert it into the database and into memory
            id = self._insert_reminder((author_id, name, when_datetime, what, channel_id, active, repeat, frequency,
                                        last_sent))
            self.reminder_dict[author_id].append({
                "id": id,
                "name": name,
                "when": when_datetime,
                "what": what,
                "channel": channel_id,
                "active": active,
                "repeat": repeat,
                "frequency": frequency,
                "last_sent": last_sent
            })
            if not repeat:
                await ctx.send(f'I will remind {name} - "{what}" at '
                           f'{when_datetime.astimezone().strftime("%a, %b %d, %Y %I:%M, %Z")}')
            else:
                await ctx.send(f'I will remind {name} - "{what}" at '
                               f'{when_datetime.astimezone().strftime("%a, %b %d, %Y %I:%M, %Z")}. This'
                               f' reminder will occur every {frequency} minute(s)!')
        except TimeoutError:
            await ctx.send('You ran out of time! Please try calling this command again! Goodbye.')

    @commands.command(name='deletereminder', aliases=['deleterem'], help='Call this instead of '
                       'updatereminder if you know the ID of the reminder you wihs to deactivate')
    async def deactivate_reminder(self, ctx, reminder_id):
        user = ctx.author.id
        if reminder_id is None:
            await ctx.send('Please try again provide a reminder ID to remove. Goodbye')
            return
        try:
            user_reminders = self.reminder_dict[user]
        except KeyError:
            await ctx.send('You have no reminders with me!')
            return

        for reminder in user_reminders:
            if str(reminder_id) == str(reminder["id"]):
                await ctx.send(f'Setting reminder id: {reminder_id} to inactive!')
                reminder["active"] = 0
                self._mark_reminder_inactive(reminder_id)
                return
        # if we made it this far then we never found a matching reminder ID, send a message and bail
        await ctx.send('I was unable to find a reminder by that ID #!')

    @commands.command(name='updatereminder', aliases=['deactivatereminder', 'updaterem', 'remupdate', 'remdeactivate'],
                      help='Let me remind you of something! call !remind and let me guide you through setting one up!')
    async def update_reminder(self, ctx):
        timeout = 60
        user = ctx.author.id
        try:
            user_reminders = self.reminder_dict[user]
        except KeyError:
            await ctx.send('You have no reminders with me!')
            return

        def check(m):
            return m.author.name == ctx.author.name

        await self.get_reminders(ctx)
        await ctx.send('Which reminder would you like to remove? Please supply the ID of the reminder.\n')

        reminder_id = await self.bot.wait_for("message", check=check, timeout=timeout)
        reminder_id = reminder_id.content

        for reminder in user_reminders:
            if str(reminder_id) == str(reminder["id"]):
                await ctx.send(f'Setting reminder id: {reminder_id} to inactive!')
                reminder["active"] = 0
                self._mark_reminder_inactive(reminder_id)
                return
        # if we made it this far then we never found a matching reminder ID, send a message and bail
        await ctx.send('I was unable to find a reminder by that ID #!')

    @commands.command(name="getreminders", aliases=['remget', 'getrem', 'reminderget', 'getreminder'],
                      help='Retrieve your current reminders in a DM!')
    async def get_reminders(self, ctx):
        new_line = '\n'
        user = ctx.author.id
        try:
            user_reminders = self.reminder_dict[user]
        except KeyError:
            await ctx.send('You have no reminders with me!')
            return
        msg = ""
        for x in user_reminders:
            for k, v in x.items():
                if x["active"] == 1:
                    if k == "frequency":
                        msg += f'{k}: {v} minute(s){new_line}'
                    elif k == "active":
                        msg += f'{k}: {ACTIVE_ENUM[v]}{new_line}'
                    elif k not in ["channel", "name"]:
                        msg += f'{k}: {v}{new_line}'
        if msg == "":
            await ctx.send('You have no active reminders with me!')
        else:
            channel = await ctx.author.create_dm()
            await channel.send(f'Here are your current active reminders:{new_line}{msg}')

    @tasks.loop(seconds=10)
    async def check_for_reminders(self):
        for user, reminders in self.reminder_dict.items():
            for reminder in reminders:
                if reminder["active"] == 1:
                    # check if its a repeat
                    if reminder["repeat"] == 0:
                        # if it's not just do a datetime check and send
                        if datetime.datetime.now() >= reminder["when"]:
                            channel = self.bot.get_channel(reminder["channel"])
                            await channel.send(f'{reminder["name"]}! This is your reminder to: {reminder["what"]}!')
                            # since it isnt a repeat reminder, mark it inactive, in memory and in the db
                            self._mark_reminder_inactive(reminder["id"])
                            reminder["active"] = 0
                    else:
                        # if it is a repeat reminder then first check the last sent, if its min we havent sent it before
                        # in this case we just need to do the when compare same as above
                        if reminder["last_sent"] == datetime.datetime.min:
                            # if now is greater then when remind, send and update last sent
                            if datetime.datetime.now() >= reminder["when"]:
                                channel = self.bot.get_channel(reminder["channel"])
                                await channel.send(f'{reminder["name"]}! This is your reminder to: {reminder["what"]}!')
                                last_sent = datetime.datetime.now()
                                self._update_last_sent_time_for_reminder_by_id(reminder["id"], last_sent)
                                reminder["last_sent"] = last_sent
                        # if last sent does not equal datetime.datetime.min and datetime.datetime.now() is greater or
                        # equal to the reminder when time + the frequency
                        elif datetime.datetime.now() >= reminder["last_sent"] + datetime.timedelta(
                                minutes=int(reminder["frequency"])):
                            channel = self.bot.get_channel(reminder["channel"])
                            await channel.send(f'{reminder["name"]}! This is your reminder to: {reminder["what"]}!')
                            last_sent = datetime.datetime.now()
                            self._update_last_sent_time_for_reminder_by_id(reminder["id"], last_sent)
                            reminder["last_sent"] = last_sent

    @check_for_reminders.before_loop
    async def before_check_for_reminders(self):
      await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def delete_inactive_reminders(self):
        self._delete_reminders()

    @delete_inactive_reminders.before_loop
    async def before_delete_inactive_reminders(self):
      await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(ReminderBot(bot))
