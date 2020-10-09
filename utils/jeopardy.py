from sqlite3 import Error
from utils.db import MarvinDB
import json
import os
from utils.helper import link_grabber, strip_tags


class Jeopardy(MarvinDB):

    QUESTION_TABLE_NAME = "jeopardy"
    QUESTION_TABLE = f"""CREATE TABLE IF NOT EXISTS {QUESTION_TABLE_NAME} (
        id integer PRIMARY KEY,
        category text NOT NULL,
        question text NOT NULL,
        worth text NOT NULL,
        answer text NOT NULL
    );"""
    INSERT_QUESTION = f"""INSERT INTO {QUESTION_TABLE_NAME}(category,question,worth,answer) VALUES(?,?,?,?)"""
    GET_RANDOM_QUESTIONS = f"""SELECT * FROM {QUESTION_TABLE_NAME} ORDER BY RANDOM() LIMIT 20;"""

    LEADERBOARD_TABLE_NAME = 'leaderboard'
    LEADERBOARD_TABLE = f"""CREATE TABLE IF NOT EXISTS {LEADERBOARD_TABLE_NAME} (
        id integer PRIMARY KEY,
        player text NOT NULL,
        worth integer NOT NULL
);"""

    INSERT_PLAYER = f"""INSERT INTO {LEADERBOARD_TABLE_NAME}(player, worth) VALUES(?,?)"""
    CHECK_IF_PLAYER_EXISTS = f"""SELECT EXISTS(SELECT * FROM {LEADERBOARD_TABLE_NAME} WHERE player=? LIMIT 1)"""
    GET_CURRENT_STANDINGS = f"""SELECT * FROM {LEADERBOARD_TABLE_NAME}"""
    UPDATE_PLAYER_SCORE = f"""UPDATE {LEADERBOARD_TABLE_NAME} SET worth = ? WHERE player=?"""
    GET_PLAYER_WORTH = f"""SELECT worth FROM {LEADERBOARD_TABLE_NAME} where player=?"""

    def __init__(self):
        super().__init__()
        try:
            self.create_table(self.conn, self.QUESTION_TABLE)
            self.create_table(self.conn, self.LEADERBOARD_TABLE)
        except Error as e:
            print(e)

    def insert_questions(self):
        json_file = os.path.dirname(os.path.dirname(__file__)) + '/data/questions.json'
        with open(json_file) as data:
            questions = json.load(data)
            cur = self.conn.cursor()
            """ It goes category, question, value, answer"""
            for question in questions:
                if question["value"] is None:
                    value = '$5000'
                else:
                    value = question["value"]

                cur.execute(
                    self.INSERT_QUESTION,
                    (question["category"],
                     self.parse_question(question["question"]),
                     value,
                     question["answer"])
                )
                self.conn.commit()

    def parse_question(self, question: str):
        new_q = []
        # check for hrefs
        links = link_grabber(question)
        if len(links) > 0:
            for link in links:
                new_q.append(link)

        # now grab the text:
        string_question = strip_tags(question)
        new_q.append(string_question)
        return "\n".join(new_q)


    def get_questions(self):
        """  returns
        id integer PRIMARY KEY,
        category text NOT NULL,
        question text NOT NULL,
        worth text NOT NULL,
        answer text NOT NULL """
        cur = self.conn.cursor()
        questions = cur.execute(self.GET_RANDOM_QUESTIONS).fetchall()
        self.conn.commit()
        return questions

    def insert_player(self, player_name, value):
        return self.insert_query(self.INSERT_PLAYER, (player_name, value))

    def check_if_player_exists(self, player_name):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_PLAYER_EXISTS, (player_name,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def update_player_score(self, value: str, player_name: str):
        """ Takes a string and plits it into an int for the database """
        value = int(value.split('$')[1].replace(',', ''))
        cur = self.conn.cursor()
        cur.execute(self.UPDATE_PLAYER_SCORE, (value, player_name))
        self.conn.commit()

    def get_leaderboard(self):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_CURRENT_STANDINGS).fetchall()
        return results

    def get_player_worth(self, player_name):
        """ Returns (id, player, worth)"""
        cur = self.conn.cursor()
        worth = cur.execute(self.GET_PLAYER_WORTH, (player_name,)).fetchone()
        return worth


if __name__ == '__main__':
    """ Run this once to seed all the question data, this will take A LONG TIME"""
    jep = Jeopardy()
    jep.insert_questions()


