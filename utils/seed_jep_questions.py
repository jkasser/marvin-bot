import os
import json
import yaml
import discord
from discord.ext import commands
from cogs.jeopardy import Jeopardy


class InsertQuestions(Jeopardy):

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
    file = open('./config.yaml', 'r')
    cfg = yaml.load(file, Loader=yaml.FullLoader)
    token = cfg["disc"]["token"]
    intents = discord.Intents().all()
    bot = commands.Bot(command_prefix=cfg["disc"]["prefix"], intents=intents)
    InsertQuestions(bot).insert_questions()