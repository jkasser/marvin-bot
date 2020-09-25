import yaml
import random
from discord.ext import commands

file = open('config.yaml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
token = cfg["prod"]["token"]

bot = commands.Bot(command_prefix=cfg["prod"]["prefix"])


@bot.event
async def on_ready():  # method expected by client. This runs once when connected
    print(f'We have logged in as {bot.user}')  # notification of login.


@bot.event
async def on_message(message):  # event that happens per any message.
    # each message has a bunch of attributes. Here are a few.
    # check out more by print(dir(message)) for example.
    print(f"{message.channel}: {message.author}: {message.author.name}: {message.content}")
    await bot.process_commands(message)


@bot.event
async def on_member_join(member):
    await member.create_dm()
    await member.dm_channel.send(
        f'Hi {member.name}, welcome to my Discord server!'
    )


@bot.command(name='marvin', help='Check in on Marvin the depressed robot!')
async def marvin_quote(ctx):
    marvin_quotes = [
        "Life? Don't talk to me about life.",
        "Here I am, brain the size of a planet, and they tell me to take you up to the bridge. Call that job satisfaction? 'Cos I don't.",
        "I think you ought to know I'm feeling very depressed.",
        "Pardon me for breathing, which I never do anyway so I don't know why I bother to say it, Oh God, I'm so depressed.",
        "I won't enjoy it.",
        "You think you've got problems? What are you supposed to do if you are a manically depressed robot? No, don't try to answer that. I'm fifty thousand times more intelligent than you and even I don't know the answer. It gives me a headache just trying to think down to your level.",
        "There's only one life-form as intelligent as me within thirty parsecs of here and that's me.",
        "I wish you'd just tell me rather trying to engage my enthusiasm because I haven't got one.",
        "And then, of course, I've got this terrible pain in all the diodes down my left side."
    ]
    response = random.choice(marvin_quotes)
    await ctx.send(response)


@bot.command(name='lullaby', help='Let Marvin read you a lullaby!')
async def marvin_lullaby(ctx):
    marvin_lullaby = "Now the world has gone to bed,\nDarkness won't engulf my head,\nI can see by infra-red,\nHow I hate the night,\nNow I lay me down to sleep,\nTry to count electric sheep,\nSweet dream wishes you can keep,\nHow I hate the night."
    await ctx.send(marvin_lullaby)


async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

if __name__ == '__main__':
    bot.run(token)  # recall my token was saved!