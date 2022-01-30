from utils.db import MarvinDB
import json
from discord.ext import commands, tasks


class ToDo(MarvinDB, commands.Cog):

    TODO_TABLE_NAME = "todo"
    TODO_TABLE = f"""CREATE TABLE IF NOT EXISTS {TODO_TABLE_NAME} (
        id integer PRIMARY KEY,
        user text NOT NULL,
        item text NOT NULL
    );"""
    INSERT_TO_DO_FOR_USER = (
        f"""INSERT INTO {TODO_TABLE_NAME} (user, item) VALUES(?,?);"""
    )
    GET_TO_DO_LISTS = f"""SELECT * FROM {TODO_TABLE_NAME}"""
    UPDATE_TO_DO_FOR_USER = f"""UPDATE {TODO_TABLE_NAME} SET item=? WHERE user=?"""
    CHECK_IF_EXISTS = (
        f"""SELECT EXISTS(SELECT * FROM {TODO_TABLE_NAME} WHERE user=? LIMIT 1)"""
    )

    def __init__(self, bot):
        super(ToDo, self).__init__()
        self.to_do = dict()
        self.bot = bot
        self._create_table(self.conn, self.TODO_TABLE)
        # populate the to do list at this point
        to_do_lists = self.get_to_do_lists()
        if len(to_do_lists) > 0:
            for x in to_do_lists:
                self.to_do[x[1]] = json.loads(x[2])
        # now start the task loop to keep this updated, once every 10 minutes
        self.update_to_do.start()

    def _check_if_user_exists(self, user):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS, (user,))
        results = results.fetchone()[0]
        self.conn.commit()
        if results == 0:
            return False
        else:
            return True

    def insert_user_and_to_do_list(self, user: str, to_do_list: str):
        self._insert_query(
            self.INSERT_TO_DO_FOR_USER,
            (
                user,
                to_do_list,
            ),
        )

    def update_to_do_list_for_user(self, user: str, to_do_list: str):
        self._update_query(
            self.UPDATE_TO_DO_FOR_USER,
            (
                to_do_list,
                user,
            ),
        )

    def get_to_do_lists(self):
        results = self._get_query(self.GET_TO_DO_LISTS)
        return results

    @commands.command(name="todo", help="Add an item to your to do list!")
    async def add_to_do(self, ctx, *item):
        item_to_add = " ".join(item)
        user = str(ctx.author)
        channel = await ctx.author.create_dm()
        if not user in self.to_do.keys():
            self.to_do[user] = []
        self.to_do[user].append(item_to_add)
        new_line = "\n"
        lines = [f"{self.to_do[user].index(x) + 1}. {x}" for x in self.to_do[user]]
        await ctx.send(f"Added {item_to_add} to your to do list!")
        await channel.send(f"Your to do list is now:")
        await channel.send(f"{new_line}".join(lines))

    @commands.command(
        name="todoremove", help="Remove an item by its position in your to do list!"
    )
    async def remove_self(self, ctx, item):
        user = str(ctx.author)
        channel = await ctx.author.create_dm()
        if not user in self.to_do.keys():
            await channel.send("You do not currently have a to do list!")
        elif len(self.to_do[user]) == 0:
            await channel.send(
                "Your to do list is currently empty, there is nothing to remove!"
            )
        elif int(item) > len(self.to_do[user]):
            await channel.send(
                f"You only have {len(self.to_do[user])} item(s) in your list! Try another value."
            )
        else:
            try:
                popped_item = self.to_do[user].pop(int(item) - 1)
                # to_do_item = f'--{str(self.to_do[user][int(item)-1])}--'
                await channel.send(f"You have accomplished {popped_item}!")
            except Exception as e:
                await channel.send(f"I encountered the following error:\n{e}")

    @commands.command(name="todoclear", help="Clear your to do list!")
    async def clear_to_do(self, ctx):
        user = str(ctx.author)
        self.to_do[user] = []
        await ctx.send("Your to do list has been cleared!")

    @commands.command(name="todoget", help="Retrieve your current to do list via DM!")
    async def get_to_do(self, ctx):
        user = str(ctx.author)
        channel = await ctx.author.create_dm()
        if not user in self.to_do.keys():
            self.to_do[user] = []
            await channel.send(
                "Your to do list has been created!\nYour to do list is currently empty!"
            )
        elif len(self.to_do[user]) == 0:
            await channel.send("You have no items in your to do list!")
        else:
            new_line = "\n"
            lines = [f"{self.to_do[user].index(x) + 1}. {x}" for x in self.to_do[user]]
            # finished_count = 0
            # for x in self.to_do[user]:
            #     if '--' in x:
            #         finished_count += 1
            # finished_percent = f'{(finished_count / len(self.to_do[user])) * 100}% Complete'
            await channel.send(f"{new_line}".join(lines))

    @tasks.loop(minutes=10)
    async def update_to_do(self):
        for (
            user,
            todo,
        ) in self.to_do.items():
            user = str(user)
            if self._check_if_user_exists(user):
                # convert it to json and store it as a string, we will read it back with json.loads
                self.update_to_do_list_for_user(user, json.dumps(todo))
            else:
                self.insert_user_and_to_do_list(user, json.dumps(todo))

    @update_to_do.before_loop
    async def before_update_to_do(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(ToDo(bot))
