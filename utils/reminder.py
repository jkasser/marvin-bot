import sqlite3
from sqlite3 import Error
import re
import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser

class ReminderBot:

    REMINDERS_TABLE = """CREATE TABLE IF NOT EXISTS reminders (
        id integer PRIMARY KEY,
        name text NOT NULL,
        when_remind timestamp NOT NULL,
        what text NOT NULL,
        channel_id integer NOT NULL,
        sent integer NOT NULL
    );"""

    INSERT_REMINDER = """INSERT INTO reminders(name,when_remind,what,channel_id,sent) VALUES(?,?,?,?,0)"""

    MARK_REMINDER_SENT = """UPDATE reminders SET sent = 1 WHERE id = ?"""

    FIND_PENDING_REMINDERS = """SELECT * FROM reminders WHERE sent=0"""

    def __init__(self):
        # if not os.path.exists('./marvin.db'):
        self.conn = None
        try:
            self.conn = sqlite3.connect('marvin.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            self.create_table(self.conn, self.REMINDERS_TABLE)
        except Error as e:
            print(e)

    def parse_reminder_text(self, string):
        name_pattern = re.compile(r'(?<=^\!remind\s)[\S]{1,}')
        when_pattern = re.compile(r'(?<=in\s|on\s).+?(?=\sto|$)')
        what_pattern = re.compile(r'(?<=to\s).+?(?=\sin|$)')

        name = name_pattern.search(string).group()
        when = when_pattern.search(string).group()
        what = what_pattern.search(string).group()
        return name, when, what

    def get_when_remind_date(self, date_string, start_time):
        if 'day' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(days=delta)
        elif 'month' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(months=+delta)
        elif 'minute' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(minutes=delta)
        elif 'second' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(seconds=delta)
        elif 'hour' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + datetime.timedelta(hours=delta)
        elif 'year' in date_string:
            delta = int(date_string.split(' ')[0].strip())
            when_remind = start_time + relativedelta(years=+delta)
        else:
            when_remind = parser.parse(date_string)
        return when_remind

    def create_table(self, conn, create_table_sql):
        try:
            c = conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(e)

    def insert_reminder(self, reminder):
        cur = self.conn.cursor()
        cur.execute(self.INSERT_REMINDER, reminder)
        self.conn.commit()
        return cur.lastrowid

    def update_reminder(self, reminder_id):
        cur = self.conn.cursor()
        cur.execute(self.MARK_REMINDER_SENT, (reminder_id,))
        self.conn.commit()

    def check_reminders(self):
        cur = self.conn.cursor()
        results = cur.execute(self.FIND_PENDING_REMINDERS)
        results = results.fetchall()
        self.conn.commit()
        return results

    def close_conn(self):
