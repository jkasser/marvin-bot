from sqlite3 import Error
import re
import datetime
import discord
from discord.ext import commands, tasks
from dateutil.relativedelta import relativedelta
from dateutil import parser
from utils.db import MarvinDB


class ReminderBot(MarvinDB, commands.Cog):

    TABLE_NAME = 'reminders'
    REMINDERS_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        name text NOT NULL,
        when_remind timestamp NOT NULL,
        what text NOT NULL,
        channel_id integer NOT NULL,
        sent integer NOT NULL
    );"""

    INSERT_REMINDER = f"""INSERT INTO {TABLE_NAME}(name,when_remind,what,channel_id,sent) VALUES(?,?,?,?,0)"""

    MARK_REMINDER_SENT = f"""UPDATE {TABLE_NAME} SET sent = 1 WHERE id = ?"""

    FIND_PENDING_REMINDERS = f"""SELECT * FROM {TABLE_NAME} WHERE sent=0"""

    def __init__(self, bot):
        self.bot = bot
        # if not os.path.exists('./marvin.db'):
        super().__init__()
        try:
            self.create_table(self.conn, self.REMINDERS_TABLE)
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
        results = results.fetchall()
        self.conn.commit()
        return results

    def parse_reminder_text(self, string):
        name_pattern = re.compile(r'(?<=^\!remind\s)[\S]{1,}')
        when_pattern = re.compile(r'(?<=in\s|on\s).*(?=\sto|\sthat)|(?<=in\s)\d{1,}.+$|(?<=\son\s).+')
        what_pattern = re.compile(r'(?<=that\s|..to\s).*(?=\son)|(?<=that\s|..to\s).*(?=\sin\s\d)|(?<=that\s|..to\s).*')

        name = name_pattern.search(string).group()
        when = when_pattern.search(string).group()
        what = what_pattern.search(string).group()
        return name, when, what

    def get_when_remind_date(self, date_string, start_time):
        if 'day' in date_string:
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(days=delta)
        elif 'month' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(months=+delta)
        elif 'minute' in date_string:
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(minutes=delta)
        elif 'second' in date_string:
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(seconds=delta)
        elif 'hour' in date_string:
            delta = float(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(hours=delta)
        elif 'year' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(years=+delta)
        else:
            when_remind = parser.parse(date_string)
        return when_remind

    @commands.command(name='remind',
                 help='Let me remind you of something! Just type \"!remind <who> in <when> to'
                      ' <what>\" NOTE: There is a minimum polling interval of 10 seconds.')
    async def create_reminder(self, ctx, *text, user: discord.Member = None):
        text = f'!remind {" ".join(text)}'
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
                           'Please use: !remind <who> in|on <when> to|that <what>.'
                           '\nDo not spell out numbers. Years and Months must be whole numbers.'
                           '\nWho must come first, when/what can come in either order.')

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
