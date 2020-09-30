import praw
from sqlite3 import Error
from utils.db import MarvinDB


class MarvinReddit(MarvinDB):

    TABLE_NAME = 'reddit'
    REDDIT_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        post_id integer NOT NULL
    );"""

    INSERT_POST = f"""INSERT INTO {TABLE_NAME}(post_id) VALUES(?)"""

    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE post_id=? LIMIT 1)"""

    def __init__(self, client_id, client_secret):
        super().__init__()
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Marvin Bot 1.0 by /u/onebagoneworld",
        )
        try:
            self.create_table(self.conn, self.REDDIT_TABLE)
        except Error as e:
            print(e)

    def add_post_id_to_db(self, post_id):
        self.insert_query(self.INSERT_POST, (post_id,))

    def check_if_post_exists(self, post_id):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS, (post_id,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def get_travel_stream(self, limit=10):
       submissions = [submission for submission in self.reddit.multireddit("OneBagOneWorld", "OneBagOneWorld").top(limit=limit)]
       if submissions is not None:
            post_list = self.parse_stream(submissions)
            return post_list

    def parse_stream(self, stream):
        post_list = []
        for submission in stream:
            if not submission.stickied:
                post_id = submission.id
                if self.check_if_post_exists(post_id):
                    # if we already have the post, just skip it
                    continue
                else:
                    self.add_post_id_to_db(submission.id)
                    post_list.append(f'{submission.title}\n{submission.selftext[:100]}...\n{submission.url}')
        return post_list
