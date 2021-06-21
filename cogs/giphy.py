import aiohttp
import json
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
        self.endpoint = '/trending'

    @commands.command(name='gif', help='Sends the top trending gif for the provided keyword(s). If no search term is '
                                       'provided then I will send a random gif', pass_context=True)
    async def post_trending(self, ctx, *search):
        print(search)
        embed = discord.Embed(colour=discord.Colour.blue())
        async with aiohttp.ClientSession() as session:
            if search == ():
                response = await session.get(f'{self.base_url}/random?api_key={self.key}')
                data = await response.json()
                embed.set_image(url=data['data']['images']['original']['url'])
            else:
                search = '+'.join(search)
                response = await session.get(
                    f'{self.base_url}/search?q={search}&api_key={self.key}&limit=1')
                data = await response.json()
                print(data)
                embed.set_image(url=data['data'][0]['images']['original']['url'])
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Giphy(bot))
