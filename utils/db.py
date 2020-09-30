import sqlite3
from sqlite3 import Error


class MarvinDB:

    def __init__(self):
        self.conn = None
        try:
            self.conn = sqlite3.connect('marvin.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        except Error as e:
            print(e)

    def create_table(self, conn, create_table_sql):
        try:
            c = conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(e)

    def insert_query(self, query, values):
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()
        return cur.lastrowid

    def update_query(self, query, values):
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()

    def get_query(self, query):
        cur = self.conn.cursor()
        results = cur.execute(query)
        results = results.fetchall()
        self.conn.commit()
        return results

    def close_conn(self):
        self.conn.close()

