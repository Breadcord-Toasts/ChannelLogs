import asyncio
import io
import logging
from enum import Enum
from typing import Awaitable, Any, Callable

import discord
from discord.ext import commands

import breadcord


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    WARN = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogLevelColour(Enum):
    DEBUG = discord.Colour.dark_gray()
    INFO = discord.Colour.blue()
    WARNING = discord.Colour.gold()
    ERROR = discord.Colour.red()
    CRITICAL = discord.Colour.dark_red()


class DiscordHandler(logging.Handler):
    def __init__(self, callback: Callable[[logging.LogRecord], Awaitable[Any]], bot: breadcord.Bot) -> None:
        super().__init__()
        self.callback = callback
        self.bot = bot

    def emit(self, record) -> None:
        if not self.bot.ready:
            return
        asyncio.create_task(self.callback(record))


class ChannelLogs(breadcord.module.ModuleCog):
    def __init__(self, module_id) -> None:
        super().__init__(module_id)
        self.channel = None
        self.ignored_exceptions: tuple[type[BaseException], ...] = (
            asyncio.CancelledError,
            commands.CommandNotFound,
            commands.NotOwner,
            commands.BadArgument,
            discord.ConnectionClosed,
        )

    async def cog_load(self) -> None:
        self.channel = await self.bot.fetch_channel(self.settings.logs_channel.value)

        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger):
                logger.addHandler(DiscordHandler(self.logging_callback, self.bot))

    async def cog_unload(self) -> None:
        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger):
                for handler in logger.handlers:
                    if isinstance(handler, DiscordHandler):
                        logger.removeHandler(handler)

    async def logging_callback(self, record: logging.LogRecord) -> None:
        if record.levelno < LogLevel[self.settings.log_level.value.upper()].value:
            return

        embed = discord.Embed(
            title="",
            colour=LogLevelColour[record.levelname].value,
            description=record.getMessage() if len(record.getMessage()) < 400 else record.getMessage()[:400] + "...",
        ).set_footer(text=record.name)

        if record.levelno > logging.WARNING:
            embed.title += "\N{NO ENTRY SIGN} "
        elif record.levelno == logging.WARNING:
            embed.title += "\N{WARNING SIGN} "
        embed.title += record.levelname.title()

        file = None
        if record.exc_info and record.exc_text:
            if record.exc_info[0] in self.ignored_exceptions:
                return

            if len(record.exc_text) < 1000:
                embed.add_field(
                    name="Traceback",
                    value=f"```py\n{record.exc_text}```",
                    inline=False,
                )
            else:
                file = discord.File(
                    filename="traceback.txt",
                    fp=io.BytesIO(record.exc_text.encode()),
                )

        await self.channel.send(embed=embed, file=file)


async def setup(bot: breadcord.Bot):
    await bot.add_cog(ChannelLogs("channel_logs"))
