import discord
from discord.ext import commands
import yaml
import os


class Reactions:
    text_channels_emoji = "💬"
    travel_emoji = "🌏"
    news_politics_emoji = "📰"
    coding_emoji = "💾"
    voice_gaming_emoji = "🎮"
    lol_emoji = "🤬"


class Roles:
    with open("config.yaml", "r") as file:
        cfg = yaml.safe_load(file)
    env = os.environ.get("ENV", "NOT SET")
    text_channels = (cfg["roles"][env]["text_channels"], "Text Channels")
    travel = (cfg["roles"][env]["travel"], "Travel Channels")
    news_and_politics = (cfg["roles"][env]["news_and_politics"], "News and Politics")
    coding = (cfg["roles"][env]["coding"], "Coding")
    voice_gaming = (cfg["roles"][env]["voice_gaming"], "Voice/Gaming Channels")
    lol = (cfg["roles"][env]["lol"], "League of Legends")


class Permissions(commands.Cog, Reactions, Roles):

    permissions_list = {
        Reactions.text_channels_emoji: Roles.text_channels,
        Reactions.travel_emoji: Roles.travel,
        Reactions.news_politics_emoji: Roles.news_and_politics,
        Reactions.coding_emoji: Roles.coding,
        Reactions.voice_gaming_emoji: Roles.voice_gaming,
        Reactions.lol_emoji: Roles.lol,
    }
