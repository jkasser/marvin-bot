from newsapi import NewsApiClient
from sqlite3 import Error
from utils.db import MarvinDB
from utils.helper import get_user_friendly_date_from_string, get_slug_from_url
from datetime import timedelta, date


class MarvinNews(MarvinDB):

    TABLE_NAME = 'news'

    NEWS_TABLE = f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id integer PRIMARY KEY,
        article_slug text NOT NULL
    );"""

    INSERT_ARTICLE = f"""INSERT INTO {TABLE_NAME}(article_slug) VALUES(?)"""

    CHECK_IF_EXISTS = f"""SELECT EXISTS(SELECT * FROM {TABLE_NAME} WHERE article_slug=? LIMIT 1)"""

    def __init__(self, key):
        super().__init__()
        try:
            self.news = NewsApiClient(api_key=key)
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

    def get_news(self, q, page_size=3, page=1):
        article_list = []
        start_date = date.today() - timedelta(days=1)
        response = self.news.get_everything(q=str(q), page_size=page_size, page=page, from_param=str(start_date))
        if response["status"] == 'ok':
            if len(response["articles"]) >= 1:
                for article in response["articles"]:
                    if self.check_if_article_exists(self.get_article_slug(article["url"])):
                        continue
                    else:
                        article_list.append(self.get_article_data(article))
                if len(article_list) == 0:
                    page = page + 1
                    return self.get_news(q=q, page_size=page_size, page=page)
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

