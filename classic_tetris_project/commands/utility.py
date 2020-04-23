import random
import math
from django.core.cache import cache
from asgiref.sync import async_to_sync
from datetime import datetime, timedelta

from .command import Command, CommandException
from ..models import Side, TwitchChannel
from ..util import Platform
from ..discord import guild_id, client as discord_client
from ..words import Words
from..util.fieldgen.field_generator import FieldGenerator
import discord as discordpy
COIN_FLIP_TIMEOUT = 10

HEADS = 0
TAILS = 1
SIDE = 2
COIN_MESSAGES = {
    HEADS: "Heads!",
    TAILS: "Tails!",
    SIDE: "Side o.O"
}

LEVELS = [48, 43, 38, 33, 28, 23, 18, 13, 8, 6, 5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]

@Command.register("hz", "hydrant", usage="hz <level> <height> <taps>")
class HzCommand(Command):

    def execute(self, level, height, taps):
        try:
            level = int(level)
            height = int(height)
            taps = int(taps)
        except ValueError:
            raise CommandException(send_usage = True)

        gravity = 1
        if (level % 256) < 29:
            gravity = LEVELS[level]

        frames = gravity * (19 - height)


        if level < 0 or height < 0 or height > 19 or taps < 1 or taps > 5:
            raise CommandException("`Unrealistic parameters.`")

        if taps == 1:
            raise CommandException("`You have {fr} frames to time this tap (and maybe a rotation for polevault).`".format(
                fr = frames
            ))

        if 2 * taps - 1 > frames:
            raise CommandException("`Not even TAS can do this.`")
        
        mini = round(60 * (taps - 1) / frames, 2)
        maxi = round(60 * taps / frames, 2)
        
        msg = "{tps} taps {hght} high on level {lvl}:\n{mini} - {maxi} Hz\n".format(
            tps=taps,
            hght=height,
            lvl=level,
            mini=mini,
            maxi=maxi
            )
        
        indices, seq = self.input_seq(frames, taps)

        if len(seq) <= 49:
            msg += "Sample input sequence: {seq}".format(seq=seq)
        else:
            msg += "Sample sequence too long. (GIF will not animate)"

        msg = "```"+msg+"```"

        self.send_message(msg)
        # get the gif. for posterity
        fg = FieldGenerator(level, height, indices)
        anim = fg.generate_image()
        picture = discordpy.File(anim, "cool_anim.gif")
        self.send_message_full(self.context.channel.id,file=picture)

    def input_seq(self, frames, taps):
        mini = frames / (taps - 1) - 0.1

        sequence = list("." * frames)
        indices = []
        for i in range(0, taps):
            indices.append(math.floor(mini * i))
            sequence[indices[i]] = 'X'

        return indices, "".join(sequence)




@Command.register("seed", "hex", usage="seed")
class SeedGenerationCommand(Command):
    def execute(self, *args):
        seed = 0
        while (seed % 0x100 < 0x3):
            seed = random.randint(0x200, 0xffffff)
        self.send_message(("RANDOM SEED: [%06x]" % seed))


@Command.register("coin", "flip", "coinflip", usage="flip")
class CoinFlipCommand(Command):

    def execute(self, *args):
        if self.context.platform == Platform.TWITCH:
            self.check_moderator()
        elif (self.context.message.guild and self.context.message.guild.id == guild_id):
            self.context.platform_user.send_message("Due to abuse, `!flip` has been disabled in the CTM Discord server.")

            self.context.delete_message(self.context.message)
            return

        if cache.get(f"flip.{self.context.user.id}"):
            return
        cache.set(f"flip.{self.context.user.id}", True, timeout=COIN_FLIP_TIMEOUT)

        o = [HEADS, TAILS, SIDE]
        w = [0.4995, 0.4995, 0.001]
        choice = random.choices(o, weights=w, k=1)[0]

        self.send_message(COIN_MESSAGES[choice])
        if choice == SIDE:
            Side.log(self.context.user)


@Command.register_discord("utc", "time", usage="utc")
class UTCCommand(Command):
    def execute(self, *args):
        t = datetime.utcnow()
        l1 = t.strftime("%A, %b %d")
        l2 = t.strftime("%H:%M (%I:%M %p)")
        self.send_message(f"Current date/time in UTC:\n**{l1}**\n**{l2}**")


@Command.register_discord("authhelp", usage="authhelp")
class AuthHelpCommand(Command):
    AUTH_HELP_STRING = (
        "Qualification authentication is a new feature of this bot. "
        "To generate a random 6-letter auth word, type `!authword`. "
        "That word will be associated with your account for 2 hours. "
        "Calling `!authword` again on any platform will return the same "
        "word. It is used for authenticating qualification attempts. "
        "You should **put the word you're assigned on the leaderboard** "
        "when you complete your first game over 5000 points. This proves "
        "that you're not playing a pre-recorded VOD.\n"
        "**NOTE:** After invoking this command, you will be barred from "
        "doing so for 48 hours. If the qualification attempt falls "
        "through due to extenuating circumstances, you will need to wait "
        "two full days before making another attempt."
    )
    def execute(self, *args):
        self.send_message(self.AUTH_HELP_STRING)


@Command.register_discord("authword", usage="authword")
class AuthWordCommand(Command):

    EXPIRE_TIME = 60 * 60 * 2      # 2 hours
    COOLDOWN_TIME = 60 * 60 * 48   # 48 hours

    def execute(self, *args):
        uid = self.context.user.id

        word = cache.get(f"authword.{uid}")
        if word is not None:
            time_left = timedelta(seconds=cache.ttl(f"authword.{uid}"))
            self.send_message(
                f"Your qualification authword is: {word.upper()}. Expires in: {time_left}"
            )
            return

        cooldown = cache.get(f"authcooldown.{uid}")
        if cooldown is not None:
            time_left = timedelta(seconds=cache.ttl(f"authcooldown.{uid}"))
            self.send_message(f"Your authword expired. Try again in: {time_left}")
            return

        authword = Words.get_word()
        cache.set(f"authword.{uid}", authword, timeout=self.EXPIRE_TIME)
        cache.set(f"authcooldown.{uid}", True, timeout=self.COOLDOWN_TIME)
        time_left = timedelta(seconds=cache.ttl(f"authword.{uid}"))
        self.send_message(
            f"Your qualification authword is: {authword.upper()}. Expires in: {time_left}"
        )


@Command.register_discord("stats", usage="stats")
class StatsCommand(Command):
    def execute(self, *args):
        self.check_moderator()

        guilds = len(discord_client.guilds)
        channels = TwitchChannel.objects.filter(connected=True).count()

        self.send_message(f"I'm in {guilds} Discord servers and {channels} Twitch channels.")
