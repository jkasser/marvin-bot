import aiohttp
import random
import yaml
import discord
from discord.ext import commands


class Giphy(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        self.key = cfg["giphy"]["key"]
        scheme = 'https'
        self.base_url = f'{scheme}://api.giphy.com/v1/gifs'
        self.gif_results_limit = 25

    @commands.command(name='gif', help='Sends the top trending gif for the provided keyword(s). If no search term is '
                                       'provided then I will send a random gif', pass_context=True)
    async def post_trending(self, ctx, *search):
        try:
            embed = discord.Embed(colour=discord.Colour.blue())
            async with aiohttp.ClientSession() as session:
                if search == ():
                    response = await session.get(f'{self.base_url}/random?api_key={self.key}')
                    data = await response.json()
                    embed.set_image(url=data['data']['images']['original']['url'])
                else:
                    search = '+'.join(search)
                    response = await session.get(
                        f'{self.base_url}/trending?q={search}&api_key={self.key}&limit={self.gif_results_limit}')
                    data = await response.json()
                    choice = random.choice(range(0, self.gif_results_limit))
                    embed.set_image(url=data['data'][int(choice)]['images']['original']['url'])
            await ctx.send(embed=embed)
        except (IndexError, KeyError):
            await ctx.send('I could\'nt find any matching results! Please try again.')


def setup(bot):
    bot.add_cog(Giphy(bot))
