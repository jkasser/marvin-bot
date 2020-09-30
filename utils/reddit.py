import praw


class MarvinReddit():

    def __init__(self, client_id, client_secret,):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="Marvin Bot 1.0 by /u/onebagoneworld",
        )

    def get_travel_stream(self, pause_after=1):
       submissions = [submission for submission in self.reddit.multireddit("OneBagOneWorld", "OneBagOneWorld").stream.submissions(pause_after=pause_after)]
       if submissions is not None:
        post_list = self.parse_stream(submissions)
        return post_list

    def parse_stream(self, stream):
        post_list = []
        for submission in stream:
            post_list.append(f'{submission.title}\n{submission.selftext}\n{submission.url}')
        return post_list
