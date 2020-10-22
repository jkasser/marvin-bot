import requests
import discord
import os
import yaml
import uuid
import json
from assets.language_codes import translate_dict, transliteration_dict
from discord.ext import commands, tasks


class MarvinTranslator(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        file = open(os.path.dirname(os.path.dirname(__file__)) + '/config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        self.key = cfg["microsoft"]["translator"]["key"]
        self.base_url = cfg["microsoft"]["translator"]["endpoint"]
        self.headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4()),
            'Ocp-Apim-Subscription-Region': 'westus2'
        }

    def check_translate_text_validity(self, text):
        # text must be less than 10K chars per request
        if len(text) >= 10000:
            return False
        else:
            return True

    def parse_response(self, response: json) -> str:
        # response should always be a list of 1 since we are only passing in one body
        response = response[0]
        confidence_score = f'{float(response["detectedLanguage"]["score"]) * 100}%'
        detected_input_language = response["detectedLanguage"]["language"]
        result = f'I have detected an input language of **{detected_input_language}** and am {confidence_score} confident' \
                 f' in my result.\n'
        for x in response["translations"]:
            language = [key for key, value in translate_dict.items() if value.lower() == x["to"].lower()]
            result += f'Translated to {language[0]}: {x["text"]}\n'
            if "transliteration" in x.keys():
                transliteration_result = x["transliteration"]["text"]
                result += f'{transliteration_result}\n'
        return result

    def check_translation_language(self, to_language):
        possible_languages = [language_key for language_key in translate_dict.keys()
                              if to_language.lower() in language_key.lower()]
        return possible_languages

    def translate_text(self, to_language: list, text):
        path = '/translate?api-version=3.0'
        params = '&suggestedFrom=en'
        for x in to_language:
            params += f'&to={x}&toScript=Latn'
        url = self.base_url + path + params
        body = [{
            "text": str(text)
        }]
        r = requests.post(url, headers=self.headers, json=body)
        if r.status_code != 200:
            return f'I have encountered the following error. {r.json()["error"]}'
        else:
            return self.parse_response(r.json())

    @commands.command(name='translate', help='Translate <destination language> <text>')
    async def marvin_translate_text(self, ctx, destination_language, * text):
        text = " ".join(text)
        if self.check_translate_text_validity(text):
            possible_langs = self.check_translation_language(destination_language)
            if len(possible_langs) >= 1:
                lang_codes = [translate_dict[code] for code in possible_langs]
                await ctx.send(f'I will attempt to translate your supplied text to: {", ".join(lang_codes)}')
                # now translate!
                translated_result = self.translate_text(lang_codes, text)
                await ctx.send(translated_result)
            else:
                await ctx.send('I was unable to find a matching language. Please call !gettranslatecodes to get a list'
                               ' of possible languages.')
                return
        else:
            await ctx.send(f'You have supplied {len(text)} chars and my max is 10,000! Please try again.')

    @commands.command(name='gettranslatecodes')
    async def get_translate_codes(self, ctx):
        codes = [language_name for language_name in translate_dict.keys()]
        await ctx.send(f'I can translate to the following languages: {", ".join(codes)}')


def setup(bot):
    bot.add_cog(MarvinTranslator(bot))
