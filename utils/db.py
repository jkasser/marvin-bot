import sqlite3
from sqlite3 import Error


class DB:
    def __init__(self):
        self.conn = None

    def _create_table(self, conn, create_table_sql):
        try:
            c = conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(e)

    def _insert_query(self, query, values):
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()
        return cur.lastrowid

    def _update_query(self, query, values):
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()

    def _get_query(self, query):
        cur = self.conn.cursor()
        results = cur.execute(query)
        results = results.fetchall()
        self.conn.commit()
        return results

    def _delete_query(self, query, value):
        cur = self.conn.cursor()
        cur.execute(query, value)
        self.conn.commit()

    def _close_conn(self):
        self.conn.close()


class MarvinDB(DB):

    SUB_USERS_TABLE_NAME = "users"
    SUB_USERS_TABLE = f"""CREATE TABLE IF NOT EXISTS {SUB_USERS_TABLE_NAME} (
        id integer PRIMARY KEY,
        user text NOT NULL,
        timezone text NOT NULL,
        disc_id integer NOT NULL
    );"""
    INSERT_USER = (
        f"""INSERT INTO {SUB_USERS_TABLE_NAME}(user, timezone, disc_id) VALUES(?,?,?)"""
    )
    UPDATE_TIMEZONE = f"""UPDATE {SUB_USERS_TABLE_NAME} SET timezone=? WHERE user=?"""
    CHECK_IF_EXISTS = (
        f"""SELECT EXISTS(SELECT * FROM {SUB_USERS_TABLE_NAME} WHERE user=? LIMIT 1)"""
    )
    GET_USER = f"""SELECT * FROM {SUB_USERS_TABLE_NAME} WHERE user=? LIMIT 1"""
    GET_ALL_USERS = f"""SELECT * FROM {SUB_USERS_TABLE_NAME}"""

    def __init__(self):
        super(MarvinDB, self).__init__()
        try:
            self.conn = sqlite3.connect(
                "marvin.db",
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=30,
                check_same_thread=False,
            )
            self._create_table(self.conn, self.SUB_USERS_TABLE)
            self.users = self._get_users()  # returns id, user, timezone
        except Error as e:
            print(e)

    def _insert_user(self, user, timezone, disc_id):
        return self._insert_query(self.INSERT_USER, (user, timezone, disc_id))

    def _update_user_tz(self, user, value):
        return self._update_query(self.UPDATE_TIMEZONE, (value, user))

    def _get_user(self, user):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_USER, (user,))
        results = results.fetchall()
        self.conn.commit()
        return results

    def _get_users(self):
        return self._get_query(self.GET_ALL_USERS)

    def _check_if_user_exists(self, user):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS, (user,))
        results = results.fetchone()[0]
        self.conn.commit()
        if results == 0:
            return False
        else:
            return True
