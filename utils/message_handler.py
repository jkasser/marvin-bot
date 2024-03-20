import re


class MessageHandler:

    MAX_CHARS = 1900
    SPLIT_POINT = 1500
    CODE_SNIPPET_RE = r"```(?:.*?)```"

    def __init__(self, message):
        self.response = []
        if len(message) < 2000:
            # just send it if we can
            self.response.append(message)
        else:
            # keep code snippets together
            self.code_snippets = []
            self.extract_code(message)
            # break up large text blocks in between
            for _ in self.code_snippets:
                self.response.extend(self.handle_large_messages(_))

    def extract_code(self, message, starting_index=0):
        try:
            match = re.search(self.CODE_SNIPPET_RE, message, re.DOTALL).group()
            first_part, remaining = message[starting_index:].split(match)
            self.code_snippets.append(first_part)
            self.code_snippets.append(match)
            # now use recursion
            self.extract_code(remaining, starting_index=message.find(remaining))
        except (AttributeError, ValueError):
            self.code_snippets.append(message)
            return

    def handle_large_messages(self, message):
        if len(message) / self.MAX_CHARS > 1:
            split_point = self.SPLIT_POINT
            for char in message[self.SPLIT_POINT:]:
                if char != '\n':
                    split_point += 1
                else:
                    break
            broken_up_response = [message[:split_point], message[split_point:]]
        else:
            broken_up_response = [message]
        return broken_up_response
