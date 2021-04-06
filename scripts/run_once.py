import sqlite3


if __name__ == '__main__':
    conn = sqlite3.connect('../marvin.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, timeout=30)
    query = """DROP TABLE reminders"""
    conn.execute(query)
    conn.commit()
    conn.close()