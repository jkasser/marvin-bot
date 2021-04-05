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

    def insert_reminder(self, values):
        return self.insert_query(self.INSERT_REMINDER, values)

    def mark_reminder_sent(self, reminder_id):
        self.update_query(self.MARK_REMINDER_SENT, (reminder_id,))

    def check_reminders(self):
        """ Returns an array of id, name, reminder time, reminder text, channel_id, has sent """
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_PENDING_REMINDERS)

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

    def get_when_remind_date(self, date_string, start_time):
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

    @commands.command(name='remind',  aliases=['rem'],
                 help='Let me remind you of something! Just type \"!remind <who> \'<what you want in single quotes\' <when>\"'
                        '\nNOTE: There is a minimum polling interval of 10 seconds.')
    async def create_reminder(self, ctx, *text, user: discord.Member = None):
        text = f"!remind {' '.join(text)}"
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

        now = datetime.datetime.now()
        user = user or ctx.author
        channel_id = ctx.message.channel.id
        try:
            # parse the string into 3 fields to insert into the database
            name, when, what = self.parse_reminder_text(text)
            if name.lower() == 'me':
                name = user.mention
            # get the date as a datetime object
            when_datetime = self.get_when_remind_date(when, start_time=now)
            # now insert it into the db
            self.insert_reminder((name, when_datetime, what, channel_id))
            await ctx.send(f'I will remind {name} - "{what}" at '
                           f'{when_datetime.astimezone().strftime("%a, %b %d, %Y %I:%M:%S, %Z")}')
        except ValueError:
            await ctx.send('ERROR: Reminder was in an invalid format! '
                           'Please use: !remind <who> \'<what you want in single quotes\' <when>'
                           '\nDo not spell out numbers. Years and Months must be whole numbers.'
                           '\nWho must come first, you must use SINGLE quotes for the what!')

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


def setup(bot):
    bot.add_cog(ReminderBot(bot))
