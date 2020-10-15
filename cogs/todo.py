from utils.db import MarvinDB
import sqlite3
from discord.ext import commands


class ToDo(MarvinDB, commands.Cog):

    TODO_TABLE_NAME = "todo"
    TODO_TABLE = f"""CREATE TABLE IF NOT EXISTS {TODO_TABLE_NAME} (
        id integer PRIMARY KEY,
        user text NOT NULL,
        item text NOT NULL,
        position integer NOT NULL
    );"""

    def __init__(self, bot):
        super(ToDo, self).__init__()
        self.to_do = {}
        self.bot = bot
        self.create_table(self.conn, self.TODO_TABLE)


    @commands.command(name='todoadd', help="Add an item to your to do list!")
    async def addto_do(self, ctx, *item):
        item_to_add = " ".join(item)
        user = ctx.author
        channel = await ctx.author.create_dm()
        if not user in self.to_do.keys():
            self.to_do[user] = []
        self.to_do[user].append(item_to_add)
        new_line = '\n'
        lines = [f"{self.to_do[user].index(x) + 1}. {x}" for x in self.to_do[user]]
        await ctx.send(f'Added {item_to_add} to your to do list!')
        await channel.send(f'Your to do list is now:')
        await channel.send(f'{new_line}'.join(lines))

    @commands.command(name='todoremove', help="Remove an item by its position in your to do list!")
    async def remove_self(self, ctx, item):
        user = ctx.author
        channel = await ctx.author.create_dm()
        if not user in self.to_do.keys():
            await channel.send('You do not currently have a to do list!')
        elif len(self.to_do[user]) == 0:
            await channel.send('Your to do list is currently empty, there is nothing to remove!')
        elif int(item) > len(self.to_do[user]):
            await channel.send(f'You only have {len(self.to_do[user])} item(s) in your list! Try another value.')
        else:
            try:
                popped_item = self.to_do[user].pop(int(item) - 1)
                await channel.send(f'You have removed {popped_item}!')
            except Exception as e:
                await channel.send(f'I encountered the following error:\n{e}')

    @commands.command(name='todoclear', help="Clear your to do list!")
    async def clear_to_do(self, ctx):
        user = ctx.author
        self.to_do[user] = []
        await ctx.send('Your to do list has been cleared!')


def setup(bot):
    bot.add_cog(ToDo(bot))
