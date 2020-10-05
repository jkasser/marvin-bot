from sqlite3 import Error
import re
import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser
from utils.db import MarvinDB


class ReminderBot(MarvinDB):

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

    def __init__(self):
        # if not os.path.exists('./marvin.db'):
        super().__init__()
        try:
            self.create_table(self.conn, self.REMINDERS_TABLE)
        except Error as e:
            print(e)

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
        when_pattern = re.compile(r'(?<=in\s|on\s).*(?=\sto|\sthat)|(?<=in\s)\d{1,}.+$|(?<=on\s).+')
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

