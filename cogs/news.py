from newsapi import NewsApiClient
from sqlite3 import Error
from utils.helper import get_user_friendly_date_from_string, get_slug_from_url, get_current_hour_of_day
from datetime import timedelta, date
import yaml
import discord
from discord.ext import commands, tasks


class MarvinNews(commands.Cog):

    TABLE_NAME = 'news'

    NEWS_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        article_slug text NOT NULL
    );"""

    INSERT_ARTICLE = f"""INSERT INTO {TABLE_NAME}(article_slug) VALUES(?)"""

    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE article_slug=? LIMIT 1)"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        file = open('config.yaml', 'r')
        self.cfg = yaml.load(file, Loader=yaml.FullLoader)
        self.key = self.cfg["news"]["key"]
        try:
            self.news = NewsApiClient(api_key=self.key)
            # self.create_table(self.conn, self.NEWS_TABLE)
        except Error as e:
            print(e)
        self.article_tracker = list()
        self.check_the_news.start()
        self.clear_post_trackers.start()

    # def add_article_to_db(self, article_slug):
    #     self.insert_query(self.INSERT_ARTICLE, (article_slug,))

    # def check_if_article_exists(self, article_slug):
    #     cur = self.conn.cursor()
    #     results = cur.execute(self.CHECK_IF_EXISTS, (article_slug,))
    #     results = results.fetchone()[0]
    #     self.conn.commit()
    #     if results == 0:
    #         return False
    #     else:
    #         return True

    def get_news(self, * q, page_size=3, page=1):
        query = " ".join(q)
        article_list = []
        start_date = date.today()
        response = self.news.get_everything(q=query, page_size=page_size, page=page, from_param=str(start_date))
        if response["status"] == 'ok':
            if len(response["articles"]) >= 1:
                for article in response["articles"]:
                    # if self.check_if_article_exists(self.get_article_slug(article["url"])):
                    article_slug = self.get_article_slug(article["url"])
                    if article_slug in self.article_tracker:
                        continue
                    else:
                        # it doesn't exist so return it to the user and append it to the dict in memory
                        article_list.append(self.get_article_data(article))
                        self.article_tracker.append(article_slug)
                if len(article_list) == 0:
                    page = page + 1
                    # pass in the original tuple since it's expecting a tuple
                    return self.get_news(q, page_size=page_size, page=page)
                else:
                    return article_list
        else:
            return f'I have encountered the following error: {response["code"]}\n{response["message"]}'

    def get_article_slug(self, url):
        return get_slug_from_url(url)

    def get_article_data(self, article: dict) -> dict:
        date_str = article["publishedAt"]
        if isinstance(article["author"], list):
            author = article["author"][0]["name"]
        else:
            author = article["author"]
        article_data = {
            "title": article["title"],
            "source": article["source"]["name"],
            "author": author,
            "description": article["description"],
            "url": article["url"],
            "thumb": article["urlToImage"],
            "published": get_user_friendly_date_from_string(date_str),
            "article_slug": self.get_article_slug(str(article["url"]))
        }
        return article_data

    @commands.command(name='getnewssources', aliases=['getsources'], help='See where I pull my news from!')
    async def get_news_sources(self, ctx):
        await ctx.send(f'I get my news from the following sources: '
                       f'{", ".join(self.cfg["news"]["sources"]).replace("-", " ").capitalize()}')

    @commands.command(name='getnews',  aliases=['checknews', 'news'],  help='Get the top 3 articles for your keyword!')
    async def get_news_for_keyword(self, ctx, * query):
        query = " ".join(query)
        news_list = self.get_news(query)
        if isinstance(news_list, list):
            for article in news_list:
                try:
                    embedded_link = discord.Embed(title=article["title"], description=article["description"],
                                                  url=article["url"])
                    embedded_link.add_field(name="Source", value=article["source"], inline=True)
                    embedded_link.add_field(name="Author", value=article["author"], inline=True)
                    embedded_link.add_field(name="Published", value=article["published"], inline=True)
                    if article["thumb"] is not "" and article["thumb"] is not None:
                        embedded_link.set_thumbnail(url=article["thumb"])
                    await ctx.send(embed=embedded_link)
                except Exception:
                    continue
        else:
            await ctx.send(f'I wasn\'t able to find anything for: {query}!')

    @tasks.loop(hours=1)
    async def check_the_news(self):
        news_channel = self.bot.get_channel(761691682383069214)
        sources = ",".join(self.cfg["news"]["sources"])
        news_list = self.news.get_top_headlines(page_size=3, sources=sources)["articles"]
        if isinstance(news_list, list):
            for post in news_list:
                # parse the article
                article = self.get_article_data(post)
                # check if the news has already been posted
                # if self.check_if_article_exists(self.get_article_slug(article["article_slug"])):
                if self.get_article_slug(article["article_slug"]) in self.article_tracker:
                    continue
                else:
                    try:
                        embedded_link = discord.Embed(title=article["title"], description=article["description"],
                                                      url=article["url"])
                        embedded_link.add_field(name="Source", value=article["source"], inline=True)
                        embedded_link.add_field(name="Author", value=article["author"], inline=True)
                        embedded_link.add_field(name="Published", value=article["published"], inline=True)
                        if article["thumb"] is not "" and article["thumb"] is not None:
                            embedded_link.set_thumbnail(url=article["thumb"])
                        await news_channel.send(embed=embedded_link)
                        # self.add_article_to_db(article["article_slug"])
                        self.article_tracker.append(article["article_slug"])
                        # remove it just in case it attempts again
                        news_list.pop(news_list.index(post))
                    except Exception:
                        continue
        else:
            await news_channel.send('I wasn\'t able to find any news!')

    @check_the_news.before_loop
    async def before_check_the_news(self):
      await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def clear_post_trackers(self):
        hour = get_current_hour_of_day()
        if hour >= 0 and hour < 1:
            # clear out our lists in memory every 24 hours, check every hour,
            self.article_tracker.clear()

    @clear_post_trackers.before_loop
    async def before_clear_post_trackers(self):
      await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(MarvinNews(bot))
