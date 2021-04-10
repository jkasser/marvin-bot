import requests
import yaml
import asyncio
from asyncio import TimeoutError
from concurrent.futures.thread import ThreadPoolExecutor
from utils.helper import validate_phone_number
from discord.ext import commands, tasks
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
        self.message_list = {}
        # TODO::: start task loop

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
            to=str(recipient),
            from_=self.from_number,
            body=str(message),
            media_url=[media]
        )
        return sent_message

    # TODO::: STUB OUT THE FOLLOWING COMMANDS: get usage, get phone number, delete phone number, marvin text feed

    @commands.has_role('Texters')
    @commands.command(name='text', help='Send a text to someone! You must get owner approval to use this command.')
    async def text(self, ctx, recipient: str, *msg):
        timeout = 60

        # probably don't use a try catch, we just want to see if the value returned is none
        # try:
        #     # TODO::: convert a contact name to a number via the address book
        #     number = f'{self.DEFAULT_COUNTRY_CODE}'
        # except:
        if not recipient.startswith('+'):
            recipient = f'{self.DEFAULT_COUNTRY_CODE}{recipient}'
        if not validate_phone_number(recipient):
            await ctx.send('Your phone number was not in a valid format! The number needs to be in a 10 digit '
                           'international format with no spaces. E.g. +12345678910\nPlease try again. Goodbye.')
            return

        msg = ' '.join(msg)
        if msg == '':
            await ctx.send('You must provide a message when you call this command! Please try again, goodbye.')
            return

        # if msg isn't none then check its length
        message_count = round(len(msg) / self.MESSAGE_LENGTH)
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
                        message_content = self.send_mms(recipient, msg, media_url)
                    else:
                        await ctx.send(f'Sorry! I only support media with the following extensions: '
                                       f'{",".join([ext for ext in self.SUPPORTED_MEDIA_TYPES])}')
                        return
                except AttributeError:
                    await ctx.send('I was unable to parse your attached media, please try this command again! Goodbye!')
                    return
            else:
                message_content = self.send_sms(recipient, msg)
            await ctx.send(f'I have attempted to send your message.\nStatus: {message_content.status}'
                           f'\nID: {message_content.sid}\nPrice: {message_content.price}')
            message_tracking = {
                message_content.sid: {"status": message_content.status, "channel_id": ctx.message.channel.id}
            }
            if ctx.author.mention not in self.message_list.keys():
                self.message_list[ctx.author.mention] = []
            self.message_list[ctx.author.mention].append(message_tracking)
        except TimeoutError:
            await ctx.send('You have taken too long! Please try again.')

    @tasks.loop(seconds=5)
    async def check_message_status(self):
        for user, messages in self.message_list.items():
            for message in messages:
                for id, results in message.items():
                    if results["status"] != 'delivered':
                        # TODO::: get status of message here?
                        continue
                    else:
                        # if it's been delivered, remove it
                        del message[id]

# TODO::: add before loop start bot ready check


def setup(bot):
    bot.add_cog(MarvinPhone(bot))
