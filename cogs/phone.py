import requests
import yaml
import asyncio
from asyncio import TimeoutError
from concurrent.futures.thread import ThreadPoolExecutor
from utils.helper import validate_phone_number
from discord.ext import commands
from twilio.rest import Client


class MarvinPhone(commands.Cog):

    MAX_MESSAGES = 5
    MESSAGE_LENGTH = 160
    DEFAULT_COUNTRY_CODE = '+1'
    SUPPORTED_MEDIA_TYPES = ('.jpg', '.gif', '.png', '.jpeg')

    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        cfg = yaml.load(file, Loader=yaml.FullLoader)
        account_sid = cfg["twilio"]["account_sid"]
        auth_token = cfg["twilio"]["auth_token"]
        self.from_number = cfg["twilio"]["number"]
        self.client = Client(account_sid, auth_token)

    def send_sms(self, recipient, message):
        # send an sms and return the twilio response
        sent_message = self.client.messages.create(
            to=recipient,
            from_=self.from_number,
            body=message
        )
        return sent_message

    def send_mms(self, recipient, message="", media=None):
        # send an mms and return the twilio response
        sent_message = self.client.messages.create(
            to=recipient,
            from_=self.from_number,
            body=message,
            media_url=[media]
        )
        return sent_message

    @commands.has_role('Texters')
    @commands.command(name='text', help='Send a text to someone! You must get owner approval to use this command.')
    async def text(self, ctx, recipient: str, msg=None):
        timeout = 60

        if recipient is None:
            await ctx.send('You must provide a recipient from your contact book with me or a phone number in the 10 '
                           'digit format with +<country code>. E.g. +12345678910. Please try again.')
            return
        else:
            # probably don't use a try catch, we just want to see if the value returned is none
            try:
                # TODO::: convert a contact name to a number via the address book
                number = f'{self.DEFAULT_COUNTRY_CODE}'
            except:
                if not validate_phone_number(recipient):
                    await ctx.send('Your phone number was not in a valid format!')

        message_count = round(len(msg) / self.MESSAGE_LENGTH)
        if msg is None:
            await ctx.send('You must provide a message when you call this command! Please try again, goodbye.')
            return
        if message_count > self.MAX_MESSAGES:
            await ctx.send('Your message is too long for me to send. I am limited to 5 messages of 160 characters each')

        def check(m):
            return m.author.name == ctx.author.name
        try:
            loop = asyncio.get_event_loop()
            await ctx.send('Do you want to attach media to this message? (Yes/Y?)')
            is_mms = await self.bot.wait_for("message", check=check, timeout=timeout)
            if is_mms.content.lower() in ('y', 'yes'):
                await ctx.send('Please upload or paste a url to the message now!')
                try:
                    mms_content = await self.bot.wait_for("message", check=check, timeout=timeout)
                    if any([mms_content.endswith(ext) for ext in self.SUPPORTED_MEDIA_TYPES]):
                        media_url = mms_content.attachments["url"]
                        message_content = await loop.run_in_executor(ThreadPoolExecutor(),
                                                                     self.send_mms, recipient, msg, media_url)
                    else:
                        await ctx.send(f'Sorry! I only support media with the following extensions: '
                                       f'{",".join([ext for ext in self.SUPPORTED_MEDIA_TYPES])}')
                        return
                except AttributeError:
                    await ctx.send('I was unable to parse your attached media, please try this command again! Goodbye!')
                    return
            else:
                message_content = await loop.run_in_executor(ThreadPoolExecutor(), self.send_sms, recipient, msg)
            await ctx.send(f'I have attempted to send your message\nStatus: {message_content.sent}'
                           f'\nID: {message_content.sid}\nPrice: {message_content.price}')
        except TimeoutError:
            await ctx.send('You have taken too long! Please try again.')


def setup(bot):
    bot.add_cog(MarvinPhone(bot))
