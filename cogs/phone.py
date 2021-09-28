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
    DELETE_MESSAGES_AFTER = 3600 # 1 hour
    DEFAULT_COUNTRY_CODE = '+1'
    SUPPORTED_MEDIA_TYPES = ('.jpg', '.gif', '.png', '.jpeg')
    FINAL_DELIVERY_STATUSES = ['delivery_unknown', 'delivered', 'undelivered', 'failed']

    def __init__(self, bot):
        self.bot = bot
        with open('config.yaml', 'r') as file:
            cfg = yaml.safe_load(file)
        account_sid = cfg["twilio"]["account_sid"]
        auth_token = cfg["twilio"]["auth_token"]
        self.from_number = cfg["twilio"]["number"]
        self.client = Client(account_sid, auth_token)
        self.sent_messages = {}
        self.check_message_status.start()

    def _send_sms(self, recipient, message):
        # send an sms and return the twilio response
        sent_message = self.client.messages.create(
            to=recipient,
            from_=self.from_number,
            body=message
        )
        return sent_message

    def _send_mms(self, recipient, message="", media=None):
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
        user = str(ctx.author)

        def check(m):
            return m.author.name == ctx.author.name
        # search results returns a dict of contact_found: bool, contact_number: str (if found) otherwise None,
        # and error_msg to print out the error
        if recipient.isalpha():
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(
                ThreadPoolExecutor(), self.bot.get_cog('AddressBook').retrieve_contacts_number, user, recipient)
            if search_results["contact_found"]:
                if len(search_results["potential_contacts"]) > 1:
                    await ctx.send(search_results["error_msg"])
                    contact_dict = {}
                    for ind, cont in enumerate(search_results["potential_contacts"]):
                        # put this into a dict we can access by key
                        contact_dict[ind] = {"name": cont[0], "number": cont[1]}

                    # print them out for the user so they can specify the index
                    for k,v in contact_dict.items():
                        await ctx.send(f'{k}: {v["name"]}')

                    contact_index = await self.bot.wait_for("message", check=check, timeout=timeout)
                    contact_index = contact_index.content
                    num = contact_dict[int(contact_index)]["number"].replace(" ", "")
                    try:
                        if num.startswith('+'):
                            recipient = num
                        else:
                            recipient = f'{self.DEFAULT_COUNTRY_CODE}{num}'
                    except KeyError:
                        await ctx.send(f'Your selection of: {contact_index} - was not valid. Please try this command '
                                       f'again. Goodbye.s')

                else:
                    num = search_results["contact_number"].replace(" ", "")
                    # we only received one potential contact at this point so just create the number
                    if num.startswith('+'):
                        recipient = num
                    else:
                        recipient = f'{self.DEFAULT_COUNTRY_CODE}{num}'
            # if the contact wasnt found then send the error message
            else:
                await ctx.send(f'{search_results["error_msg"]}')
                return
        else:
            recipient = recipient.replace(" ", "")
            if not recipient.startswith('+'):
                recipient = f'{self.DEFAULT_COUNTRY_CODE}{recipient}'
            if not validate_phone_number(recipient):
                await ctx.send('Your phone number was not in a valid format! Please try again. Goodbye.')
                return

        msg = ' '.join(msg)
        if msg == '':
            await ctx.send('You must provide a message when you call this command! Please try again, goodbye.')
            return

        # if msg isn't none then check its length
        message_count = round(len(msg) / self.MESSAGE_LENGTH)
        if message_count > self.MAX_MESSAGES:
            await ctx.send('Your message is too long for me to send. I am limited to 5 messages of 160 characters each')

        # try:
        #     await ctx.send('Do you want to attach media to this message? (Yes/Y?)')
        #     is_mms = await self.bot.wait_for("message", check=check, timeout=timeout)
        #     if is_mms.content.lower() in ('y', 'yes'):
        #         await ctx.send('Please upload or paste a url to the message now!')
        #         try:
        #             mms_content = await self.bot.wait_for("message", check=check, timeout=timeout)
        #             if any([mms_content.endswith(ext) for ext in self.SUPPORTED_MEDIA_TYPES]):
        #                 media_url = mms_content.content
        #                 message_content = self._send_mms(recipient, msg, media_url)
        #             else:
        #                 await ctx.send(f'Sorry! I only support media with the following extensions: '
        #                                f'{",".join([ext for ext in self.SUPPORTED_MEDIA_TYPES])}')
        #                 return
        #         except AttributeError:
        #             await ctx.send('I was unable to parse your attached media, please try this command again! Goodbye!')
        #             return
        #     else:
        message_content = self._send_sms(recipient, msg)
        # store what we need in a dict so we can edit the message later
        sent_message = await ctx.send(f'I have attempted to send your message.\nStatus: {message_content.status}'
                                      f'\nID: {message_content.sid}\nPrice: {message_content.price}')
        message_tracking = {message_content.sid: {
            "status": message_content.status,
            "channel_id": ctx.message.channel.id,
            "message_id": sent_message.id,
            "price": message_content.price}}
        if ctx.author.mention not in self.sent_messages.keys():
            self.sent_messages[ctx.author.mention] = []
        self.sent_messages[ctx.author.mention].append(message_tracking)
        # except TimeoutError:
        #     await ctx.send('You have taken too long! Please try again.')

    @tasks.loop(seconds=5)
    async def check_message_status(self):
        for user, messages in self.sent_messages.items():
            for text in messages:
                for id, results in text.items():
                    if results["status"] not in self.FINAL_DELIVERY_STATUSES:
                        response = self.client.messages(id).fetch()
                        results["status"] = response.status
                        if response.status in self.FINAL_DELIVERY_STATUSES:
                            # we are in a final delivery state, update the message id
                            channel = self.bot.get_channel(int(results["channel_id"]))
                            message = await channel.fetch_message(results["message_id"])
                            await message.edit(content=f'**UPDATE FOR YOUR MESSAGE TO: {response.to}.**\n'
                                                       f'Status: **{results["status"].upper()}**\nID: {id}'
                                                       f'\nPrice: {response.price} ({response.price_unit})\n'
                                                       f'This message will be deleted in '
                                                       f'{int(float(self.DELETE_MESSAGES_AFTER/3600))} hour.',
                                               delete_after=self.DELETE_MESSAGES_AFTER)
                            messages.remove(text)
                    else:
                        # if we somehow made it this far
                        messages.remove(text)
                        continue

    @check_message_status.before_loop
    async def before_check_message_status(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(MarvinPhone(bot))
