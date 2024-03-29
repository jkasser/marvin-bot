import requests
import os
import yaml
import uuid
import json
import asyncio
from assets.language_codes import translate_dict
from discord.ext import commands
from concurrent.futures.thread import ThreadPoolExecutor


class MarvinTranslator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open(
            os.path.dirname(os.path.dirname(__file__)) + "/config.yaml", "r"
        ) as file:
            cfg = yaml.safe_load(file)
        self.key = cfg["microsoft"]["translator"]["key"]
        self.base_url = cfg["microsoft"]["translator"]["endpoint"]
        self.headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
            "Ocp-Apim-Subscription-Region": "eastus2",
        }

    def _check_translate_text_validity(self, text):
        # text must be less than 10K chars per request
        if len(text) >= 10000:
            return False
        else:
            return True

    def _parse_response(self, response: json) -> str:
        # response should always be a list of 1 since we are only passing in one body
        response = response[0]
        confidence_score = f'{float(response["detectedLanguage"]["score"]) * 100}%'
        detected_input_language = response["detectedLanguage"]["language"]
        input_lang = [
            lang
            for lang, key in translate_dict.items()
            if key.lower() == detected_input_language.lower()
        ][0]
        result = (
            f"I have detected an input language of **{input_lang}** and am {confidence_score} confident"
            f" in my result.\n"
        )
        for x in response["translations"]:
            language = [
                key
                for key, value in translate_dict.items()
                if value.lower() == x["to"].lower()
            ]
            result += f'Translated to {language[0]}: {x["text"]}\n'
            if "transliteration" in x.keys():
                transliteration_result = x["transliteration"]["text"]
                result += f"{transliteration_result}\n"
        return result

    def _check_translation_language(self, to_language):
        possible_languages = [
            language_key
            for language_key in translate_dict.keys()
            if to_language.lower() in language_key.lower()
        ]
        return possible_languages

    def _translate_text(self, to_language: list, text):
        path = "/translate?api-version=3.0"
        params = "&suggestedFrom=en"
        for x in to_language:
            params += f"&to={x}&toScript=Latn"
        url = self.base_url + path + params
        body = [{"text": str(text)}]
        r = requests.post(url, headers=self.headers, json=body)
        if r.status_code != 200:
            return f'I have encountered the following error. {r.json()["error"]}'
        else:
            return self._parse_response(r.json())

    @commands.command(
        name="translate",
        aliases=["tlate", "trans"],
        help="Translate <destination language> <text>",
    )
    async def marvin_translate_text(self, ctx, destination_language, *text):
        text = " ".join(text)
        if self._check_translate_text_validity(text):
            possible_langs = self._check_translation_language(destination_language)
            if len(possible_langs) >= 1:
                lang_strings = [code for code in possible_langs]
                lang_codes = [translate_dict[code] for code in possible_langs]
                await ctx.send(
                    f'I will attempt to translate your supplied text to: {", ".join(lang_strings)}'
                )
                # now translate!
                loop = asyncio.get_event_loop()
                translated_result = await loop.run_in_executor(
                    ThreadPoolExecutor(), self._translate_text, lang_codes, text
                )
                await ctx.send(translated_result)
            else:
                await ctx.send(
                    "I was unable to find a matching language. Please call !gettranslatecodes to get a list"
                    " of possible languages."
                )
                return
        else:
            await ctx.send(
                f"You have supplied {len(text)} chars and my max is 10,000! Please try again."
            )

    @commands.command(name="gettranslatecodes", aliases=["getlangs"])
    async def get_translate_codes(self, ctx):
        codes = [language_name for language_name in translate_dict.keys()]
        await ctx.send(
            f'I can translate to the following languages: {", ".join(codes)}'
        )


def setup(bot):
    bot.add_cog(MarvinTranslator(bot))
