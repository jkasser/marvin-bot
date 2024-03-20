import os
import yaml
from openai import AsyncOpenAI
from discord.ext import commands
from utils.message_handler import MessageHandler


class MarvinAI(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.named_queues = dict(General=[])
        with open("config.yaml", "r") as file:
            cfg = yaml.safe_load(file)
        env = os.environ.get("ENV", "NOT SET")
        self.ai_channel = cfg["disc"][env]["ai_channel"]
        self.ai_model = cfg["ai"]["model"]
        ai_key = cfg["ai"]["key"]
        self.instructions = cfg["ai"]["instructions"]
        self.ai_client = AsyncOpenAI(
            api_key=ai_key
        )

    @commands.has_any_role("Server Booster", "Family", "Admins")
    @commands.Cog.listener("on_message")
    async def ai_message(self, message):
        if message.channel.id == self.ai_channel and not message.author.bot and not message.content.startswith('!'):
            gpt_response = await self.ai_client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {
                        "role": "system",
                        "content": self.instructions,
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


async def setup(bot):
    await bot.add_cog(MarvinAI(bot))
