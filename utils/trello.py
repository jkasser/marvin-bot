import requests


class Trello:

    def __init__(self, trello_key, trello_token, board_id):
        self.api_key = trello_key
        self.callback = 'https://discordapp.com/api/webhooks/765259094319169596/ybtENsIHT-b7dOyRyCbeycjGfQicbYTdN5bNufocc42z7C3tYekYTlBuQWqcuncg3cPS'
        self.api_token = trello_token
        self.base_url = f'https://api.trello.com/1/tokens/{self.api_token}/webhooks/?key={trello_key}'
        self.params = {
            "callbackURL": self.callback,
            "description": "Marvin Trello",
            "idModel": str(board_id),
        }
        self.headers = {
            "Content-Type": "application/json"
        }

    def post_webhook(self):
        r = requests.post(self.base_url, params=self.params, headers=self.headers)
        return r

    def delete_webhook(self, id):
        url = f'https://api.trello.com/1/webhooks/{id}?key={self.api_key}&token={self.api_token}'
        r = requests.delete(url)
        return r

    def get_webhook(self):
        r = requests.get(self.base_url)
        return r

