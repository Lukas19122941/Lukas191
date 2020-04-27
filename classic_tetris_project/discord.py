import discord
import logging
from .env import env

client = discord.Client()
guild_id = int(env("DISCORD_GUILD_ID", default=0))
moderator_role_id = int(env("DISCORD_MODERATOR_ROLE_ID", default=0))
logger = logging.getLogger("discord-bot")

def get_guild():
    return client.get_guild(guild_id)

def get_channel(id):
    return client.get_channel(id)

def get_emote(name):
    r = discord.utils.get(get_guild().emojis, name=name)
    return str(r) if r else None
def get_emoji(name):
    return get_emote(name)
