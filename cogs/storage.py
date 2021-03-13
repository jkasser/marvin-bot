import yaml
import fabric
from discord.ext import commands, tasks
from concurrent.futures.thread import ThreadPoolExecutor


class Storage(commands.Cog):

    MAX_SIZE = 1000000
    ROOT = '~/CloudStation/'

    def __init__(self, bot):
        self.bot = bot
        file = open('config.yaml', 'r')
        self.cfg = yaml.load(file, Loader=yaml.FullLoader)
        host = self.cfg["ssh"]["host"]
        un = self.cfg["ssh"]["un"]
        pw = self.cfg["ssh"]["pw"]
        port = 22
        self.ssh = fabric.Connection(
            f"{un}@{host}:{port}", connect_kwargs={"password": pw},
        )
        self.move_to_dir = f'cd {self.ROOT}'


    def run(self, command, warn=True, hide=True):
        output = self.ssh.run(command, warn=warn, hide=hide)
        return output

    def convert_size(self, size_to_convert):
        return f'{float(int(size_to_convert) / 1024)} MB'

    def size_check(self, name):
        cmd_to_execute = f'du -s {self.ROOT}{name}/ -k'
        output = self.run(cmd_to_execute)
        current_size = output.stdout.split()[0]
        if int(current_size) < self.MAX_SIZE:
            return f'Your current usage is: {self.convert_size(current_size)}'
        else:
            return f'You are over the allotted size of {self.convert_size(self.MAX_SIZE)}!'

    def check_if_bucket_exists(self, name):
        cmd_to_execute = f'{self.ROOT}{name} -d'
        output = self.run(cmd_to_execute)
        if 'Is a directory' in output.stderr:
            return True
        elif 'No such file or directory' in output.stderr:
            return False
        else:
            # edge case handling
            return False

    def make_bucket_for_user(self, name):
        cmd_to_execute = f'mkdir {self.ROOT}{name}'
        self.run(cmd_to_execute)

    def get_bucket_contents(self, name):
        cmd_to_execute = f'ls {self.ROOT}{name}/'
        output = self.run(cmd_to_execute)
        return output.stdout

    @commands.has_any_role("Admins", "Family")
    @commands.command(name='makebucket', help="Create a folder for yourself with marvin!")
    async def make_bucket(self, ctx):
        if self.check_if_bucket_exists(ctx.author.id):
            await ctx.send('This bucket already exists!')
        else:
            self.make_bucket_for_user(ctx.author.id)
            await ctx.send('Your bucket has been created! You have up to 1gb of storage capabilities with me.')

    @commands.has_any_role("Admins", "Family")
    @commands.command(name='store', help="Store an item on marvin's server.")
    async def marvin_store_item(self, ctx):
        if self.check_if_bucket_exists(ctx.author.id):
            await ctx.send(self.size_check(ctx.author.id))
        else:
            await ctx.send('You do not currently have a bucket, let me create one for you.')
            await ctx.invoke(self.bot.get_command('makebucket'))
        # figure how the fuck to do this
        pass

    @commands.has_any_role("Admins", "Family")
    @commands.command(name='retrieve', help="Store an item on marvin's server.")
    async def marvin_store_item(self, ctx):
        if self.check_if_bucket_exists(ctx.author.id):
            await ctx.send(self.size_check(ctx.author.id))
        else:
            await ctx.send('You do not currently have a bucket, let me create one for you.')
            await ctx.invoke(self.bot.get_command('makebucket'))
        # figure how the fuck to do this
        pass

    @commands.has_any_role("Admins", "Family")
    @commands.command(name='storesize', help="See how much size you have left with marvin!")
    async def marvin_get_user_storage_capacity(self, ctx):
        if self.check_if_bucket_exists(ctx.author.id):
            await ctx.send(self.size_check(ctx.author.id))
        else:
            await ctx.send('You do not currently have a bucket, let me create one for you.')
            await ctx.invoke(self.bot.get_command('makebucket'))

    @commands.has_any_role("Admins", "Family")
    @commands.command(name='storecontents', help="See what you currently have stored with marvin")
    async def marvin_get_user_storage_contents(self, ctx):
        if self.check_if_bucket_exists(ctx.author.id):
            await ctx.send('I will dm you this for privacy!')
            channel = await ctx.author.create_dm()
            contents = self.get_bucket_contents(ctx.author.id)
            if contents == "":
                await channel.send('Your bucket is empty!')
            else:
                await channel.send(contents)
        else:
            await ctx.send('You do not currently have a bucket, let me create one for you.')
            await ctx.invoke(self.bot.get_command('makebucket'))


def setup(bot):
    bot.add_cog(Storage(bot))
