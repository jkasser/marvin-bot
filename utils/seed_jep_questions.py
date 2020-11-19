import os
import json
from cogs.jeopardy import Jeopardy
from utils.db import MarvinDB


class InsertQuestions(MarvinDB):

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
                    Jeopardy.INSERT_QUESTION,
                    (question["category"],
                     Jeopardy.parse_question(question["question"]),
                     value,
                     question["answer"])
                )
                self.conn.commit()

if __name__ == '__main__':
    InsertQuestions().insert_questions()