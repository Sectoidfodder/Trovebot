import traceback
import sys
import os
import asyncio
from dotenv import load_dotenv
from configparser import ConfigParser
from discord.ext import commands
from automod.automod import AutoMod
from records.records import Records
from utils import autoping

trovebot = commands.Bot('t!')
config = ConfigParser()
config.read('trovebot.ini')
load_dotenv()
automod = AutoMod(trovebot, config['AutoMod'])
records = Records(trovebot, config['Records'])

@trovebot.event
async def on_ready():
    print('Logged in as {}'.format(trovebot.user))

@trovebot.event
async def on_command_error(ctx, err):
    if hasattr(ctx.command, 'on_error'):
        return
    ignored = (commands.CommandOnCooldown, commands.CommandNotFound, commands.CheckFailure, commands.MissingRequiredArgument, commands.BadArgument)
    if isinstance(err, ignored):
        return
    print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
    traceback.print_exception(type(err), err, err.__traceback__, file=sys.stderr)

@trovebot.command()
@commands.is_owner()
async def echo(ctx):
    await ctx.send('echo')

@trovebot.command()
@commands.is_owner()
async def reload_config(ctx):
    config.read('trovebot.ini')
    automod.config = config['AutoMod']
    records.config = config['Records']
    print('config reloaded')

@trovebot.command()
@commands.is_owner()
async def shutdown(ctx):
    await trovebot.logout()

async def periodic_save():
    while True:
        await asyncio.sleep(1800)
        await automod.save()
        await records.save()
        print('periodic save')

autoping.autoping()

trovebot.add_cog(automod)
trovebot.add_cog(records)
trovebot.loop.create_task(periodic_save())
trovebot.run(os.getenv('TOKEN'))