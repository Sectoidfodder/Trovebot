import re
import pickle
import os
from typing import List, Dict
from datetime import datetime
from discord.ext import commands
from discord import Activity, ActivityType, TextChannel, Member

class Reminder:
    channelid: int
    interval: int
    text: str
    count: int
    def __init__(self, channel, interval, text):
        self.channelid = channel
        self.interval = interval
        self.text = text
        self.count = 0
    
class Monitor:
    #channel ids to monitor, or all channels if empty
    channels: List[int]
    #any condition that is not None is checked
    has_blacklisted_ign: bool
    has_image: bool
    regex: str
    negate_regex: bool
    #any action that is not None or False is performed
    log: str
    reply: str
    dm: str
    delete: bool
    mute: bool
    restrict: bool
    def __init__(self, channels = []):
        self.channels = channels
        self.has_blacklisted_ign = None
        self.has_image = None
        self.regex = None
        self.negate_regex = False
        self.log = None
        self.reply = None
        self.dm = None
        self.delete = False
        self.mute = False
        self.restrict = False
    def __str__(self):
        return (
            '**Conditions**\n'
            f'channels: `{self.channels if len(self.channels) > 0 else "ALL"}`\n'
            f'blacklist: `{self.has_blacklisted_ign}`\n'
            f'image: `{self.has_image}`\n'
            f'regex: `{self.regex}`\n'
            f'negate: `{self.negate_regex}`\n'
            '**Actions**\n'
            f'alert: `{self.log}`\n'
            f'reply: `{self.reply}`\n'
            f'dm: `{self.dm}`\n'
            f'delete: `{self.delete}`\n'
            f'mute: `{self.mute}`\n'
            f'restrict: `{self.restrict}`')

class AutoModData:
    reminders: Dict[str, Reminder]
    banned_igns: List[str]
    monitors: Dict[str, Monitor]
    def __init__(self):
        self.reminders = {}
        self.banned_igns = []
        self.monitors = {}

class AutoMod(commands.Cog):
    data: AutoModData
    def __init__(self, bot, config):
        self.bot = bot
        try:
            with open('automod/automod.pickle', 'rb') as f:
                self.data = pickle.load(f)
                print('automod data successfully loaded')
        except:
            self.data = AutoModData()
            print('failed to load automod data')
        self.config = config

    async def _send_warning(self, warning):
        warningchannel = self.bot.get_channel(self.config.getint('WarningID', -1))
        await warningchannel.send(warning)

    async def _mute(self, member):
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        role = guild.get_role(self.config.getint('Muted'))
        await member.add_roles(role)

    async def _restrict(self, member):
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        role = guild.get_role(self.config.getint('TradeRestricted'))
        await member.add_roles(role)

    def _match_conditions(self, message, monitor):
        match = 'n/a'
        if len(monitor.channels) > 0 and message.channel.id not in monitor.channels:
            return None
        if monitor.has_blacklisted_ign != None:
            hasign = False
            lowercontent = message.content.lower()
            for ign in self.data.banned_igns:
                if ign.lower() in lowercontent:
                    hasign = True
                    match = ign
                    break
            if hasign != monitor.has_blacklisted_ign:
                return None
        if monitor.has_image != None:
            hasimg = False
            for a in message.attachments:
                if a.height != None:
                    hasimg = True
                    break
            if hasimg != monitor.has_image:
                return None
        if monitor.regex != None:
            regexmatch = re.search(monitor.regex, message.content, re.IGNORECASE)
            if regexmatch != None:
                match = regexmatch[0]
            hasmatch = True if regexmatch != None else False
            if hasmatch == monitor.negate_regex:
                return None
        return match
    
    def _replace_tags(self, target, message, match):
        tempstr = target
        tempstr = tempstr.replace('{author}', message.author.name)
        tempstr = tempstr.replace('{authormention}', message.author.mention)
        tempstr = tempstr.replace('{channel}', message.channel.name)
        tempstr = tempstr.replace('{channelmention}', message.channel.mention)
        tempstr = tempstr.replace('{messagelink}', f'<{message.jump_url}>')
        tempstr = tempstr.replace('{match}', match)
        return tempstr

    async def _perform_actions(self, message, monitor, match):
        if monitor.log != None:
            await self._send_warning(self._replace_tags(monitor.log, message, match))
        if monitor.reply != None:
            #await self._send_warning(f'reply in {message.channel.mention}: ' + self._replace_tags(monitor.reply, message, match))
            await message.channel.send(self._replace_tags(monitor.reply, message, match))
        if monitor.dm != None:
            #await self._send_warning(f'dm {message.author.mention}: ' + self._replace_tags(monitor.dm, message, match))
            await message.author.send(self._replace_tags(monitor.dm, message, match))
        if monitor.mute:
            #await self._send_warning(f'mute {message.author.mention}')
            await self._mute(message.author)
        if monitor.restrict:
            #await self._send_warning(f'restrict {message.author.mention}')
            await self._restrict(message.author)
        if monitor.delete:
            #await self._send_warning(f'delete in {message.channel.mention}')
            await message.delete()

    async def _checkmonitors(self, message):
        if not isinstance(message.author, Member):
            return
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        exemptrole = guild.get_role(self.config.getint('Exempt'))
        if exemptrole != None and message.author.top_role > exemptrole:
            return
        for monitor in self.data.monitors.values():
            match = self._match_conditions(message, monitor)
            if match != None:
                await self._perform_actions(message, monitor, match)

    async def _checkreminders(self, message):
        for reminder in self.data.reminders.values():
            if message.channel.id == reminder.channelid:
                reminder.count += 1
            if reminder.count >= reminder.interval:
                await message.channel.send(reminder.text)
                reminder.count = 0

    def _get_channels(self, ctx, mentions):
        channellist = []
        for mention in mentions:
            try:
                channel = ctx.guild.get_channel(int(mention[2:len(mention)-1]))
                if channel != None:
                    channellist.append(channel)
            except:
                pass
        return channellist

    ###########LISTENERS##########

    @commands.Cog.listener()
    async def on_ready(self):
        print('automod ready')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print('on_member_join')
        accountage = datetime.utcnow().date() - member.created_at.date()
        if accountage.days <= int(os.getenv('NEWUSER_RESTRICT')):
            traderestricted = self.bot.get_guild(self.config.getint('GuildID')).get_role(self.config.getint('TradeRestricted'))
            await member.add_roles(traderestricted)
            await self._send_warning(f'New account {member.mention} joined, created {accountage.days} days ago (trade restricted)')
            await member.send(
                'You have been trade-restricted on TFT.\n'
                'In order to gain access to our trade channels, please DM our ModMail with proof that you own a real PoE account.')
        elif accountage.days <= int(os.getenv('NEWUSER_WARN')):
            await self._send_warning(f'New account {member.mention} joined, created {accountage.days} days ago')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await self._checkmonitors(message)
        await self._checkreminders(message)

    ###########COMMANDS###########

    @commands.group()
    async def reminders(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if ctx.invoked_subcommand == None:
            summary = 'No reminders set' if len(self.data.reminders) == 0 else '\n'.join([f'{k} in <#{v.channelid}> every {v.interval} messages.' for k, v in self.data.reminders.items()])
            await ctx.message.channel.send(summary)

    @reminders.command(name = 'add')
    async def reminders_add(self, ctx, name: str, channel: TextChannel, interval: int, text: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if channel == None:
            await ctx.message.channel.send('Invalid channel')
        elif interval < 1:
            await ctx.message.channel.send('Invalid interval')
        elif name in self.data.reminders.keys():
            await ctx.message.channel.send('A reminder with that name already exists')
        else:
            self.data.reminders[name] = Reminder(channel.id, interval, text)
            await ctx.message.channel.send(f'Reminder {name} will be sent to {channel.mention} every {interval} messages')

    @reminders.command(name = 'remove')
    async def reminders_remove(self, ctx, name: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.reminders.keys():
            await ctx.message.channel.send(f'There is no reminder named {name}')
        else:
            self.data.reminders.pop(name)
            await ctx.message.channel.send(f'Removed reminder {name}')

    @commands.group()
    async def blacklist(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if ctx.invoked_subcommand == None:
            await ctx.message.channel.send(str(self.data.banned_igns))

    @blacklist.command(name = 'add')
    async def blacklist_add(self, ctx, ign: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if ign in self.data.banned_igns:
            await ctx.message.channel.send(f'{ign} is already banned')
        else:
            self.data.banned_igns.append(ign)
            await ctx.message.channel.send(f'{ign} added to banlist')

    @blacklist.command(name = 'remove')
    async def blacklist_remove(self, ctx, ign: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if ign in self.data.banned_igns:
            self.data.banned_igns.remove(ign)
            await ctx.message.channel.send(f'{ign} removed from banlist')
        else:
            await ctx.message.channel.send(f'{ign} not found in banlist')

    @commands.group()
    async def monitors(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if ctx.invoked_subcommand == None:
            await ctx.send(f'Registered monitors: {self.data.monitors.keys()}')

    @monitors.command(name = 'add')
    async def monitors_add(self, ctx, name: str, *mentions):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name in self.data.monitors.keys():
            await ctx.send('There is already a monitor with that name')
        else:
            channelids = [c.id for c in self._get_channels(ctx, mentions)]
            self.data.monitors[name] = Monitor(channelids)
            await ctx.send(f'Monitor {name} created')
    
    @monitors.command(name = 'remove')
    async def monitors_remove(self, ctx, name: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors.pop(name)
            await ctx.send(f'Monitor {name} deleted')
    
    @monitors.command(name = 'info')
    async def monitors_info(self, ctx, name: str):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            await ctx.send(str(self.data.monitors[name]))
    
    @monitors.group(name = 'edit')
    async def monitors_edit(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
    
    @monitors_edit.command(name = 'channels')
    async def monitors_edit_channels(self, ctx, name: str, *mentions):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            channels = self._get_channels(ctx, mentions)
            self.data.monitors[name].channels = [c.id for c in channels]
            await ctx.send(f'Monitor {name}, channels: {[c.mention for c in channels]}')

    @monitors_edit.command(name = 'blacklist')
    async def monitors_edit_blacklist(self, ctx, name: str, blacklist: bool = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].has_blacklisted_ign = blacklist
            await ctx.send(f'Monitor {name}, blacklist: `{blacklist}`')

    @monitors_edit.command(name = 'image')
    async def monitors_edit_image(self, ctx, name: str, image: bool = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].has_image = image
            await ctx.send(f'Monitor {name}, image: `{image}`')

    @monitors_edit.command(name = 'regex')
    async def monitors_edit_regex(self, ctx, name: str, regex: str = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].regex = regex
            await ctx.send(f'Monitor {name}, regex: `{regex}`')
            print(regex)

    @monitors_edit.command(name = 'negate')
    async def monitors_edit_negate(self, ctx, name: str, negate: bool = False):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].negate_regex = negate
            await ctx.send(f'Monitor {name}, negate: `{negate}`')

    @monitors_edit.command(name = 'alert')
    async def monitors_edit_log(self, ctx, name: str, log: str = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].log = log
            await ctx.send(f'Monitor {name}, alert: `{log}`')

    @monitors_edit.command(name = 'reply')
    async def monitors_edit_reply(self, ctx, name: str, reply: str = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].reply = reply
            await ctx.send(f'Monitor {name}, reply: `{reply}`')
    
    @monitors_edit.command(name = 'dm')
    async def monitors_edit_dm(self, ctx, name: str, dm: str = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].dm = dm
            await ctx.send(f'Monitor {name}, dm: `{dm}`')
    
    @monitors_edit.command(name = 'delete')
    async def monitors_edit_delete(self, ctx, name: str, delete: bool = False):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].delete = delete
            await ctx.send(f'Monitor {name}, delete: `{delete}`')
    
    @monitors_edit.command(name = 'mute')
    async def monitors_edit_mute(self, ctx, name: str, mute: bool = False):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].mute = mute
            await ctx.send(f'Monitor {name}, mute: `{mute}`')
    
    @monitors_edit.command(name = 'restrict')
    async def monitors_edit_restrict(self, ctx, name: str, restrict: bool = False):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if name not in self.data.monitors.keys():
            await ctx.send('There is no monitor with that name')
        else:
            self.data.monitors[name].restrict = restrict
            await ctx.send(f'Monitor {name}, restrict: `{restrict}`')

    @commands.command()
    @commands.is_owner()
    async def save_automod(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        with open('automod/automod.pickle', 'wb') as f:
            pickle.dump(self.data, f)
        print('automod data saved')

    @commands.command()
    @commands.is_owner()
    async def echo_automod(self, ctx):
        await ctx.channel.send('automod ready')