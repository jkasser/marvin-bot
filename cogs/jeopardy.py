import json
import os
import random
from discord.ext import commands, tasks
from asyncio import TimeoutError
from sqlite3 import Error
from utils.db import MarvinDB
from utils.helper import link_grabber, strip_tags, fuzz_compare_answers, update_current_worth


class Jeopardy(MarvinDB, commands.Cog):

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

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.question_list = []
        self.leaderboard = {}
        try:
            self.create_table(self.conn, self.QUESTION_TABLE)
            self.create_table(self.conn, self.LEADERBOARD_TABLE)
        except Error as e:
            print(e)
        # this has to come after the DB create since we grab the values from the database
        standings = self.get_leaderboard()
        for standing in standings:
            db_player = standing[1]
            db_worth = f'${standing[2]}'
            self.leaderboard[db_player] = db_worth
        self.update_jep_leaderboard.start()

    @staticmethod
    def parse_question(question: str):
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
        int_value = int(value.split('$')[1].replace(',', ''))
        return self.insert_query(self.INSERT_PLAYER, (player_name, int_value))

    def check_if_player_exists(self, player_name):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_PLAYER_EXISTS, (player_name,))
        results = results.fetchone()[0]
        self.conn.commit()
        if results == 0:
            return False
        else:
            return True

    def update_player_score(self, player_name: str, value: str):
        """ Takes a string and plits it into an int for the database """
        value = int(value.split('$')[1].replace(',', ''))
        cur = self.conn.cursor()
        cur.execute(self.UPDATE_PLAYER_SCORE, (value, player_name))
        self.conn.commit()

    def get_leaderboard(self):
        cur = self.conn.cursor()
        results = cur.execute(self.GET_CURRENT_STANDINGS).fetchall()
        self.conn.commit()
        return results

    def get_player_worth(self, player_name):
        """ Returns (id, player, worth)"""
        cur = self.conn.cursor()
        worth = cur.execute(self.GET_PLAYER_WORTH, (player_name,)).fetchone()
        self.conn.commit()
        return worth

    @commands.command(name='playjep', aliases=['jep'], help='Play a round of jeopardy!')
    async def play_jeopardy(self, ctx):
        current_player = ctx.author.name
        if ctx.channel.category_id != 764524003075031050:
            await ctx.send(f'Please use this over in any of the channels in the Jeopardy category!')
            return
        else:
            timeout = 60
            # Once we get to 5 questions left, retrieve another 20, store them in memory
            if len(self.question_list) <= 5:
                questions = self.get_questions()
                for question in questions:
                    question_dict = {
                        "id": question[0],
                        "category": question[1],
                        "question": self.parse_question(question[2]),
                        "worth": question[3],
                        "answer": question[4]
                    }
                    self.question_list.append(question_dict)
            # create a new contestant or welcome someone back
            msg = ('Let\'s play!\n')
            if len(self.leaderboard) != 0:
                if current_player in self.leaderboard.keys():
                    worth = self.leaderboard[current_player]
                    msg += (f'I see you are back for more {current_player}!\nYour current worth is: {worth}\n')
                else:
                    msg += 'Welcome new contestant!\n'
                    self.leaderboard[current_player] = "$0"
            else:
                msg += 'Welcome new contestant!\n'
                self.leaderboard[current_player] = "$0"
            await ctx.send(msg)
            # now ask a random question
            question_to_ask = random.choice(self.question_list)
            q_msg = f'Category: **{question_to_ask["category"]}**\nValue: ** ' \
                   f'{question_to_ask["worth"]}**\nQuestion: **{question_to_ask["question"]}**\n'
            q_msg += f'You have **{timeout}** seconds to answer starting now!'
            await ctx.send(q_msg)
            # remove the question from the list in memory
            self.question_list.pop(self.question_list.index(question_to_ask))

        # await for the response and check the answer
        def check(m):
            return m.author.name == ctx.author.name
        try:
            user_answer = await self.bot.wait_for("message", check=check, timeout=timeout)
            user_answer = user_answer.content
        except TimeoutError:
            await ctx.send('BZZZZ! You have run out of time!')
            user_answer = ""
        correctness = fuzz_compare_answers(question_to_ask["answer"], user_answer)
        await ctx.send(f'The correct answer is: **{question_to_ask["answer"]}**\nYou answered: **{user_answer}**')
        await ctx.send(f'Your answer is: **{correctness}%** correct.')
        # determine correctness and update leaderboard, polling task will update scores in the DB every 5 minutes
        if correctness >= 60:
            await ctx.send(f'We will consider that a valid answer, you have just earned {question_to_ask["worth"]}')
            new_worth = update_current_worth(self.leaderboard, current_player, question_to_ask["worth"])
            await ctx.send(f'Your worth is now: {new_worth}')
        else:
            await ctx.send(f'That was not correct!')
            lost_worth = f'$-{question_to_ask["worth"].split("$")[1]}'
            new_worth = update_current_worth(self.leaderboard, current_player, lost_worth)
            await ctx.send(f'Your worth is now: {new_worth}')

    @commands.command('jepstandings', help='See the current standings!')
    async def get_jep_standings(self, ctx):
        await ctx.send(f'**Player**: **Worth**')
        for current_player, current_worth in self.leaderboard.items():
            await ctx.send(f'{current_player}: {current_worth}')

    @tasks.loop(minutes=10)
    async def update_jep_leaderboard(self):
        # every 10 minutes update the database with our leaderboard in memory
        for player, worth in self.leaderboard.items():
            # ignore if its 0, we will get a division error
            # check if player is in the database
            if self.check_if_player_exists(player):
                if worth != "$0":
                    self.update_player_score(player, worth)
            else:
                self.insert_player(player, worth)

    @update_jep_leaderboard.before_loop
    async def before_update_jep_leaderboard(self):
      await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Jeopardy(bot))
