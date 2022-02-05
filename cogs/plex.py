import yaml
import asyncio
import requests
from asyncio import TimeoutError
from concurrent.futures.thread import ThreadPoolExecutor
from discord.ext import commands, tasks


class MarvinMedia(commands.Cog):
    NO_IP_ERR = 'No IP is currently set, wait for the agent to check in first.'

    def __init__(self):
        with open('config.yaml', 'r') as file:
            cfg = yaml.safe_load(file)
        self.host = None
        self.port = cfg["tv"]["port"]
        # keep track of last message ID, purge every 5 minutes of inactivity
        self.last_message_id = None

    def _get_host_ip(self):
        if self.host is None:
            msg = self.NO_IP_ERR
        else:
            msg = str(self.host)
        return msg

    @commands.command('plexget', help='Get a list of active downloads!')
    async def get_current_dls(self, ctx):
        host = self._get_host_ip()
        if host != self.NO_IP_ERR:
            try:
                r = requests.get(f'{host}:{self.port}/get-all')
                if r.status_code == 200:
                    return
                else:
                    await ctx.send(f'We have experienced an issue: {r.status_code}\n{r.text}')
            except Exception as e:
                await ctx.send(e)
        else:
            await ctx.send(host)

    @commands.command('plexpauseall', help='Pause active downloads!')
    async def pause_current_dls(self, ctx):
        host = self._get_host_ip()
        if host != self.NO_IP_ERR:
            try:
                r = requests.get(f'{host}:{self.port}/pause-all')
                if r.status_code == 200:
                    return
                else:
                    await ctx.send(f'We have experienced an issue: {r.status_code}\n{r.text}')
            except Exception as e:
                await ctx.send(e)
        else:
            await ctx.send(host)
