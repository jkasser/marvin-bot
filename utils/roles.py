import discord
from discord.ext import commands


class Reactions:
    text_channels_emoji = "💬"
    travel_emoji = "🌏"
    news_politics_emoji = "📰"
    coding_emoji = "💾"
    voice_gaming_emoji = "🎮"
    lol_emoji = "🤬"


class Roles:
    text_channels = (1175090001885790309, "Text Channels")
    travel = (1175095586110845040, "Travel Channels")
    news_and_politics = (1175096549013999637, "News and Politics")
    coding = (1175097189782003732, "Coding")
    voice_gaming = (1175094986316980332, "Voice/Gaming Channels")
    lol = (1175093620450267167, "League of Legends")


class Permissions(commands.Cog, Reactions, Roles):

    permissions_list = {
        Reactions.text_channels_emoji: Roles.text_channels,
        Reactions.travel_emoji: Roles.travel,
        Reactions.news_politics_emoji: Roles.news_and_politics,
        Reactions.coding_emoji: Roles.coding,
        Reactions.voice_gaming_emoji: Roles.voice_gaming,
        Reactions.lol_emoji: Roles.lol,
    }

