from newsapi import NewsApiClient
import calendar
import praw
from sqlite3 import Error
from utils.db import MarvinDB


class MarvinNews(NewsApiClient, MarvinDB):

    TABLE_NAME = 'news'

    NEWS_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        article_slug text NOT NULL
    );"""

    INSERT_ARTICLE = f"""INSERT INTO {TABLE_NAME}(article_slug) VALUES(?)"""

    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE article_slug=? LIMIT 1)"""


    def __init__(self):
        super().__init__()
        try:
            self.create_table(self.conn, self.NEWS_TABLE)
        except Error as e:
            print(e)

    def add_article_to_db(self, article_slug):
        self.insert_query(self.INSERT_ARTICLE, (article_slug,))

    def check_if_article_exists(self, article_slug):
        cur = self.conn.cursor()
        results = cur.execute(self.CHECK_IF_EXISTS, (article_slug,))
        results = results.fetchone()[0]
        if results == 0:
            return False
        else:
            return True

    def get_news(self, q):
        article_list = []
        response = self.get_everything(q=str(q), page_size=3)
        if response["status"] == 'ok':
            articles = response["articles"]
            if len(articles) >= 1:
                for article in articles:
                    article_list.append(self.get_article_data(article))
            return article_list
        else:
            return f'We have encountered the following error: {response["code"]}\n{response["message"]}'

    def get_article_slug(self, url):
        return f'{url.strip("/").split("/")}'

    def get_article_data(self, article: dict) -> dict:
        date_str = article["publishedAt"]
        article_data = {
            "title": article["title"],
            "source": article["source"]["name"],
            "author": article["author"],
            "description": article["description"],
            "url": article["url"],
            "thumb": article["urlToImage"],
            "published": f'{calendar.month_name[int(date_str.split("-")[1])]} {date_str.split("-")[2].split("T")[0]}, {date_str.split("-")[0]}',
            "article_slug": self.get_article_slug(str(article["url"]))
        }
        return article_data

