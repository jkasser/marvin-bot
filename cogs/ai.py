import yaml
from utils.db import MarvinDB
from openai import AsyncOpenAI
from discord.ext import commands
from utils.message_handler import MessageHandler


class MarvinAI(commands.Cog, MarvinDB):
    TABLE_NAME = "ai_instructions"

    # field names
    DISCORD_ID = "disc_id"
    INSTRUCTIONS = "instructions"

    def __init__(self, bot):
        super(MarvinAI, self).__init__()
        self.bot = bot
        with open("config.yaml", "r") as file:
            cfg = yaml.safe_load(file)
        self.ai_model = cfg["ai"]["model"]
        ai_key = cfg["ai"]["key"]
        self.default_instructions = cfg["ai"]["instructions"]
        self.ai_client = AsyncOpenAI(
            api_key=ai_key
        )
        # set the table
        self.instruction_sets = self.select_collection(self.TABLE_NAME)

        # Cache for instructions
        self.instructions_cache = {}
        self._set_current_instructions_cache()

    def _set_current_instructions_cache(self):
        instructions = self.run_find_many_query(self.instruction_sets, query_to_run={})
        if instructions is not None:
            for instruction in instructions:
                self.instructions_cache[instruction[self.DISCORD_ID]] = instruction[self.INSTRUCTIONS]

    @commands.has_any_role("Server Booster", "Family", "Admins")
    @commands.Cog.listener("on_message")
    async def ai_message(self, message):
        if not message.author.bot and not message.content.startswith('!') and message.content.lower().startswith('marvin'):
            # check if we have custom instructions
            user_id = str(message.author.id)
            if user_id in self.instructions_cache:
                user_instructions = self.instructions_cache[user_id]
            else:
                user_instructions = self.instruction_sets.find_one({self.DISCORD_ID: user_id})
                if user_instructions:
                    # set it in the cache if it hasn't been added
                    self.instructions_cache[user_id] = user_instructions[self.INSTRUCTIONS]
                    user_instructions = user_instructions[self.INSTRUCTIONS]
                else:
                    user_instructions = self.default_instructions

            gpt_response = await self.ai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {
                        "role": "system",
                        "content": user_instructions,
                    },
                    {
                        "role": "user",
                        "content": f"""{message.content}"""
                    },
                ],
            )
            reply_id = await message.channel.fetch_message(message.id)
            for _ in MessageHandler(gpt_response.choices[0].message.content.strip()).response:
                await reply_id.reply(_)

    @commands.has_any_role("Server Booster", "Family", "Admins")
    @commands.command(
        name="setgpt",
        help="Tell Marvin how you would like it to respond to you",
    )
    async def set_instructions(self, ctx, *, instructions):
        user_id = str(ctx.author.id)
        existing_record = self.instruction_sets.find_one({self.DISCORD_ID: user_id})

        if existing_record:
            self.instruction_sets.update_one(
                {self.DISCORD_ID: user_id},
                {"$set": {self.INSTRUCTIONS: f"""{instructions}"""}}
            )
        else:
            self.instruction_sets.insert_one(
                {self.DISCORD_ID: user_id, self.INSTRUCTIONS: f"""{instructions}"""}
            )

        # Update the cache
        self.instructions_cache[user_id] = instructions

        await ctx.send(f"Your instructions have been set, {ctx.author.name}. Marvin is not enthusiastic about this.")


async def setup(bot):
    await bot.add_cog(MarvinAI(bot))
