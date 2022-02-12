import yaml
import uuid
import json
import boto3
import os
from discord.ext import commands, tasks


class MarvinMedia(commands.Cog):
    NO_IP_ERR = 'No IP is currently set, wait for the agent to check in first.'

    def __init__(self, bot):
        with open('config.yaml', 'r') as file:
            cfg = yaml.safe_load(file)
        self.bot = bot
        self.queue_url = cfg["plex"]["sqs_queue"]
        self.msg_q_id = cfg["plex"]["message_group_id"]
        self.sqs = boto3.client(
        "sqs",
        region_name=cfg["plex"]["region"],
        aws_access_key_id=cfg["plex"]["aws_key_id"],
        aws_secret_access_key=cfg["plex"]["aws_secret_id"]
    )
        # we will only post to a specific channel
        env = os.environ.get("ENV", "NOT SET")
        self.plex_channel_id = cfg["disc"][env]["plex_channel"]
        self.purge_all.start()

    def _send_command_to_sqs(self, command, data=None):
        response = self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"command": command, "data": data}),
            MessageGroupId=self.msg_q_id,
            MessageDeduplicationId=str(uuid.uuid4())
        )
        return response

    @commands.has_role('Family')
    @commands.command('plexget', help='Get a list of active media!')
    async def get_current_dls(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='get-all')
        print(response)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexpauseall', help='Pause all active media!')
    async def pause_current_dls(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='pause-all')
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexpauseone', help='Pause a specified hash!')
    async def pause_one(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='pause-one', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexresumeall', help='Resume all active media!')
    async def resume_all(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='resume-all')
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexresumeone', help='Resume a specified hash!')
    async def resume_one(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='resume-one', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexdownload', help='Download specified media!')
    async def download_link(self, ctx, link):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if link is None:
            await self.disc_channel.send('You must provide a link.')
            return
        response = self._send_command_to_sqs(command='download-link', data=str(link))
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexforcestart', help='Force start all active media!')
    async def force_start(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='force-start')
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexdelete', help='Delete the specified hash!')
    async def delete_one(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='delete-one', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plextagtv', help='Tag the specified hash as tv!')
    async def tag_tv(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='tag-tv', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plextagmovie', help='Tag the specified hash as movie!')
    async def tag_movie(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='tag-movie', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexprocess', help='Process the specified hash!')
    async def process_file(self, ctx, hash):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        if hash is None:
            await self.disc_channel.send('You must provide a hash, call plexget to see a list of all current hashes.')
            return
        response = self._send_command_to_sqs(command='process-file', data=hash)
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexstartapp', help='Start the application!')
    async def start_app(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='start')
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @commands.has_role('Family')
    @commands.command('plexconenct', help='Connect to the application!')
    async def start_app(self, ctx):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        response = self._send_command_to_sqs(command='connect')
        await self.disc_channel.send(
            f'Message {response["MessageId"]} sent. Response status: {response["ResponseMetadata"]["HTTPStatusCode"]}'
        )

    @tasks.loop(minutes=30)
    async def purge_all(self):
        self.disc_channel = self.bot.get_channel(int(self.plex_channel_id))
        await self.disc_channel.send('Purging all messages!')
        await self.disc_channel.purge()
        await self.disc_channel.send('Purge complete. Next purge in 30 minutes!')

    @purge_all.before_loop
    async def before_purge_all(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(MarvinMedia(bot))
