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
                    if unit in self.TIME_UNITS:
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
            await ctx.send('Now, in how long would you like to be reminded? If this is a repeat reminder, '
                           'this will be the time from which I calculate all subsequent reminders. '
                           'E.g. 2 days, 4 hours, now')
            # wait for the user to reply
            start_reminder = await self.bot.wait_for("message", check=check, timeout=timeout)
            start_reminder = start_reminder.content
            when_datetime = self._get_when_remind_date(start_reminder, start_time=now)

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
                               f' reminder will occur every {frequency} minutes!')
        except TimeoutError:
            await ctx.send('You ran out of time! Please try calling this comamnd again! Goodbye.')

    @tasks.loop(seconds=10)
    async def check_for_reminders(self):
        results = self.check_reminders()
        if len(results):
            # results are a tuple of index, name, when, what, channel_id, and sent
            for result in results:
                # check the when date to see if its => now
                if datetime.datetime.now() >= result[2]:
                    channel = self.bot.get_channel(result[4])
                    await channel.send(f'{result[1]}! This is your reminder to: {result[3]}!')
                    # set it as sent
                    self.mark_reminder_sent(result[0])

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
