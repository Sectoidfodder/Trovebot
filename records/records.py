import pickle
import asyncio
import os
from typing import Dict
from datetime import datetime
from discord import Member, Message, Colour, Embed, File
from discord.ext import commands
from records.memberdata import MemberData
from utils import snowflake

class RecordsData:
    member_db: Dict[int, MemberData]
    timestamp_vouch: datetime
    timestamp_rep: datetime
    def __init__(self):
        self.member_db = {}
        self.timestamp_vouch = datetime.min
        self.timestamp_rep = datetime.min

class Records(commands.Cog):
    _DEFAULT_COLOR = Colour.from_rgb(70, 240, 10)
    _WARNING_COLOR = Colour.from_rgb(240, 240, 10)
    _SAFE_COLOR = Colour.from_rgb(0, 120, 0)

    data: RecordsData
    _message_lock_vouch: bool
    _message_lock_rep: bool

    def __init__(self, bot, config):
        self.bot = bot
        try:
            with open('records/records.pickle', 'rb') as f:
                self.data = pickle.load(f)
                print('records data successfully loaded')
        except:
            self.data = RecordsData()
            print('failed to load records data')
        self.config = config
        self._message_lock_vouch = True
        self._message_lock_rep = True

    async def _check_promotions(self, id: int):
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        member = guild.get_member(id)
        if member == None:
            return
        if not self._message_lock_vouch:
            summary = (0, 0, 0)
            if id in self.data.member_db.keys():
                summary = self.data.member_db[id].get_vouch_summary()
            channel = guild.get_channel(self.config.getint('VouchTrackingID'))
            for roleid, req in eval(self.config.get('VouchRoles')):
                role = guild.get_role(roleid)
                if summary[0] >= req and not role in member.roles:
                    await member.add_roles(role)
                    await channel.send(f'{member.mention} promoted to {role.name}!')
                    #print(f'promoting {member.name} to {role.name}')
        if not self._message_lock_rep:
            summary = (0, 0, 0)
            if id in self.data.member_db.keys():
                summary = self.data.member_db[id].get_rep_summary()
            channel = guild.get_channel(self.config.getint('RepTrackingID'))
            for roleid, req in eval(self.config.get('RepRoles')):
                role = guild.get_role(roleid)
                if summary[0] >= req and not role in member.roles:
                    await member.add_roles(role)
                    await channel.send(f'{member.mention} promoted to {role.name}!')
                    #print(f'promoting {member.name} to {role.name}')

    async def _check_demotions(self, id: int):
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        member = guild.get_member(id)
        if member == None:
            return
        channel = guild.get_channel(self.config.getint('WarningID'))
        if not self._message_lock_vouch:
            summary = (0, 0, 0)
            if id in self.data.member_db.keys():
                summary = self.data.member_db[id].get_vouch_summary()
            for roleid, req in eval(self.config.get('VouchRoles')):
                role = guild.get_role(roleid)
                if summary[0] < req and role in member.roles:
                    await channel.send(f'{member.mention} edited/deleted below requirement for {role.name}')
        if not self._message_lock_rep:
            summary = (0, 0, 0)
            if id in self.data.member_db.keys():
                summary = self.data.member_db[id].get_rep_summary()
            for roleid, req in eval(self.config.get('RepRoles')):
                role = guild.get_role(roleid)
                if summary[0] < req and role in member.roles:
                    await channel.send(f'{member.mention} edited/deleted below requirement for {role.name}')

    async def _check_warnings(self, id: int):
        channel = self.bot.get_channel(self.config.getint('WarningID'))
        vouchmsgs = self.data.member_db[id].vouch_msgs
        if vouchmsgs[-1][2] >= os.getenv('MENTIONS_WARN'):
            await channel.send(f'<@{id}> vouched 10+ times in one message by <@{vouchmsgs[-1][1]}>')
        vouchercheck = os.getenv('VOUCHER_CHECK_PER')
        if len(vouchmsgs) % vouchercheck == 0:
            newvouchers = set()
            count = 0
            for msg in vouchmsgs[-1:(-1-vouchercheck):-1]:
                if snowflake.time_diff(msg[1], msg[0]) // (60 * 60 * 24) < os.getenv('VOUCHER_CHECK_AGE'):
                    newvouchers.add(msg[1])
                    count += 1
            if count >= os.getenv('VOUCHER_CHECK_THRESHOLD'):
                vouchermentions = ', '.join([f'<@{v}>' for v in newvouchers])
                await channel.send(f'<@{id} {count}/{vouchercheck} most recent vouches from new accounts: {vouchermentions}')

    async def _track_vouch(self, message: Message, checks: bool = False):
        freqtable = {}
        for memberid in message.raw_mentions:
            freqtable[memberid] = freqtable.get(memberid, 0) + 1
        for memberid, count in freqtable.items():
            if memberid == message.author.id:
                continue
            if not memberid in self.data.member_db.keys():
                self.data.member_db[memberid] = MemberData(memberid)
            self.data.member_db[memberid].add_vouch((message.id, message.author.id, count))
            if checks:
                await self._check_promotions(memberid)
                await self._check_warnings(memberid)
        #don't mess with timestamps until bot is done processing backlog from on_ready
        if not self._message_lock_vouch:
            self.data.timestamp_vouch = max(self.data.timestamp_vouch, message.created_at)
    
    async def _track_rep(self, message: Message, checks: bool = False):
        freqtable = {}
        for memberid in message.raw_mentions:
            freqtable[memberid] = freqtable.get(memberid, 0) + 1
        for memberid, count in freqtable.items():
            if memberid == message.author.id:
                continue
            if not memberid in self.data.member_db.keys():
                self.data.member_db[memberid] = MemberData(memberid)
            self.data.member_db[memberid].add_rep((message.id, message.author.id, count))
            if checks:
                await self._check_promotions(memberid)
                await self._check_warnings(memberid)
        #don't mess with timestamps until bot is done processing backlog from on_ready
        if not self._message_lock_rep:
            self.data.timestamp_rep = max(self.data.timestamp_rep, message.created_at)
    
    async def _untrack_vouch(self, msgid: int, checks: bool = False):
        for mid, mdata in self.data.member_db.items():
            msg = mdata.remove_vouch(msgid)
            if msg != None and checks:
                await self._check_demotions(mid)

    async def _untrack_rep(self, msgid: int, checks: bool = False):
        for mid, mdata in self.data.member_db.items():
            msg = mdata.remove_rep(msgid)
            if msg != None and checks:
                await self._check_demotions(mid)

    async def update_leaderboard(self):
        print('checking leaders')
        leaders = [(k, v.get_vouch_summary()[0]) for k, v in self.data.member_db.items()]
        leaders = sorted(leaders, key=lambda x: x[1], reverse=True)
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        toprole = guild.get_role(self.config.getint('TopRole'))
        secondrole = guild.get_role(self.config.getint('SecondRole'))
        topold = set()
        secondold = set()
        for m in guild.members:
            if toprole in m.roles:
                topold.add(m)
            if secondrole in m.roles:
                secondold.add(m)
        topnew = set()
        secondnew = set()
        minvouches = 70
        toplimit = self.config.getint('TopRoleLimit')
        secondlimit = self.config.getint('SecondRoleLimit')
        leaderstxt = '**Top Service Providers:**'
        n = 0
        for i in range(len(leaders)):
            if n >= secondlimit + 5:
                break
            member = guild.get_member(leaders[i][0])
            if member == None:
                print(f'skipped {leaders[i][0]} not in guild')
                continue
            if n < toplimit and leaders[i][1] >= minvouches:
                topnew.add(member)
            if n < secondlimit and leaders[i][1] >= minvouches:
                secondnew.add(member)
            n += 1
            leaderstxt += f'\n{n}. {member.display_name} ({leaders[i][1]})'
        topremove = topold - topnew
        for m in topremove:
            if secondrole.id not in self.data.member_db[m.id].legacy_roles:
                print(f'alpha rm {m.name}')
                await m.remove_roles(toprole)
        topadd = topnew - topold
        for m in topadd:
            print(f'alpha add {m.name}')
            await m.add_roles(toprole)
        secondremove = secondold - secondnew
        for m in secondremove:
            if secondrole.id not in self.data.member_db[m.id].legacy_roles:
                print(f'eternal rm {m.name}')
                await m.remove_roles(secondrole)
        secondadd = secondnew - secondold
        for m in secondadd:
            print(f'eternal add {m.name}')
            await m.add_roles(secondrole)
        channel = self.bot.get_channel(self.config.getint('VouchLeadersChannelID'))
        try:
            message = await channel.fetch_message(self.config.getint('VouchLeadersMessageID'))
            await message.edit(content=leaderstxt)
            print('leaderboard updated')
        except:
            message = await channel.send(leaderstxt)
            print('leaderboard created')

    async def _build_vouch_embed(self, member: Member):
        accountdays = abs((datetime.utcnow().date()-member.created_at.date()).days)
        serverdays = abs((datetime.utcnow().date()-member.joined_at.date()).days)
        toprole = member.top_role
        vouchstats = (0, 0, 0)
        paststats = (0, 0, 0)
        if member.id in self.data.member_db.keys():
            vouchstats = self.data.member_db[member.id].get_vouch_summary()
            paststats = self.data.member_db[member.id].get_vouch_history()
        reasons = []
        sidecolor = self._DEFAULT_COLOR
        label = self.config.get('DefaultRank')
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        warningrole = guild.get_role(self.config.getint('WarningRole'))
        saferole = guild.get_role(self.config.getint('SafeRole'))
        if accountdays < self.config.getint('WarningAge'):
            reasons.append('New Discord account')
        if serverdays < self.config.getint('WarningMemberAge'):
            reasons.append('Recently joined TFT')
        if toprole <= warningrole:
            reasons.append('Has no earned role in TFT')
        if len(reasons) > 0:
            sidecolor = self._WARNING_COLOR
            label = self.config.get('WarningRank')
        if toprole >= saferole:
            sidecolor = self._SAFE_COLOR
            label = self.config.get('SafeRank')
            reasons = ['Has a highly trusted role in TFT']
        fulldescription = label
        if len(reasons) > 0:
            fulldescription += ': ' + ', '.join(reasons)
        embed = Embed(
            title = str(member) + (f', AKA "{member.display_name}"' if member.display_name != member.name else ''),
            description = fulldescription,
            colour = sidecolor
        )
        embed.add_field(name='Account age', value = f'{accountdays} days', inline=True)
        embed.add_field(name='Member duration', value = f'{serverdays} days', inline=True)
        embed.add_field(name='Highest role', value = toprole, inline = False)
        embed.add_field(name='Heist Services', value = f'**{vouchstats[0]}** unique users\n**{vouchstats[1]}** different sessions\n**{vouchstats[2]}** total vouches', inline=True)
        embed.add_field(name='Past Services', value = f'**{paststats[0]}** unique users\n**{paststats[1]}** different sessions\n**{paststats[2]}** total vouches', inline=True)
        return embed
    
    async def _build_rep_embed(self, member: Member):
        msgids = []
        repcount = 0
        if member.id in self.data.member_db.keys():
            msgids = self.data.member_db[member.id].get_recent_rep(self.config.getint('ShowRecentRep'))
            repcount = self.data.member_db[member.id].get_rep_summary()[2]
        repchannel = self.bot.get_channel(self.config.getint('RepTrackingID'))
        msgtexts = []
        for msgid in msgids:
            try:
                rawmsg = await repchannel.fetch_message(msgid)
                date = rawmsg.created_at.date().strftime('%m/%d')
                msgtexts.append(f'[{date}] {rawmsg.author}: {rawmsg.clean_content}')
            except:
                msgtexts.append(f'<Error retrieving message {msgid}')
        fullmsg = '\n'.join(msgtexts)
        if len(fullmsg) > 1900:
            fullmsg = fullmsg[:1900] + '...'
        if len(fullmsg) == 0:
            fullmsg = '<No rep messages>'
        guild = self.bot.get_guild(self.config.getint('GuildID'))
        midrole = guild.get_role(self.config.getint('RepMidRole'))
        highrole = guild.get_role(self.config.getint('RepHighRole'))
        if highrole in member.roles:
            sidecolor = self._SAFE_COLOR
        elif midrole in member.roles:
            sidecolor = self._DEFAULT_COLOR
        else:
            sidecolor = self._WARNING_COLOR
        embed = Embed(
            title = str(member) + (f', AKA "{member.display_name}"' if member.display_name != member.name else ''),
            description = f'**{repcount}** rep received',
            colour = sidecolor
        )
        embed.add_field(name='Most recent', value = fullmsg)
        return embed

    async def save(self):
        with open('records/records.pickle', 'wb') as f:
            pickle.dump(self.data, f)
        print('records data saved')

    ###########LISTENERS##########

    @commands.Cog.listener()
    async def on_ready(self):
        print('retrieving missed rep...')
        #channel lookup sometimes fails while bot is starting so try a few times
        channelid = self.config.getint('RepTrackingID')
        for i in range(3):
            channel = self.bot.get_channel(channelid)
            if channel == None:
                print(f'channel {channelid} not found')
                await asyncio.sleep(3)
            else:
                break
        if channel == None:
            print(f'skipped catching up on rep')
        else:
            print(f'channel {channel.name}, last saved {self.data.timestamp_rep}')
            count = 0
            async for message in channel.history(limit=100000, after=self.data.timestamp_rep, oldest_first=True):
                await self._track_rep(message)
                count += 1
                if count % 1000 == 0:
                    print(count)
            print(f'{count} rep processed')
        self._message_lock_rep = False

        print('retrieving missed vouches...')
        channelid = self.config.getint('VouchTrackingID')
        for i in range(3):
            channel = self.bot.get_channel(channelid)
            if channel == None:
                print(f'channel {channelid} not found')
                await asyncio.sleep(3)
            else:
                break
        if channel == None:
            print(f'skipped catching up on vouches')
        else:
            print(f'channel {channel.name}, last saved {self.data.timestamp_vouch}')
            count = 0
            async for message in channel.history(limit=100000, after=self.data.timestamp_vouch, oldest_first=True):
                await self._track_vouch(message)
                count += 1
                if count % 1000 == 0:
                    print(count)
            print(f'{count} vouches processed')
        self._message_lock_vouch = False
        
        print('records ready')

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return
        if message.channel.id == self.config.getint('VouchTrackingID'):
            if len(message.raw_mentions) == 0:
                #print('no user mention in message')
                await message.channel.send(f'{message.author.mention} I can\'t find a user mention in your message. Please make sure the user name you are vouching is recognized by Discord (a blue link).')
            else:
                await self._track_vouch(message, True)
        if message.channel.id == self.config.getint('RepTrackingID'):
            if len(message.raw_mentions) == 0:
                #print('no user mention in message')
                await message.channel.send(f'{message.author.mention} I can\'t find a user mention in your message. Please make sure the user name you are vouching is recognized by Discord (a blue link).')
            else:
                await self._track_rep(message, True)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if payload.channel_id == self.config.getint('VouchTrackingID'):
            await self._untrack_vouch(payload.message_id, True)
            channel = self.bot.get_channel(self.config.getint('VouchTrackingID'))
            message = await channel.fetch_message(payload.message_id)
            await self._track_vouch(message, True)
            print(f'edited vouch {payload.message_id}')
        elif payload.channel_id == self.config.getint('RepTrackingID'):
            await self._untrack_rep(payload.message_id, True)
            channel = self.bot.get_channel(self.config.getint('RepTrackingID'))
            message = await channel.fetch_message(payload.message_id)
            await self._track_rep(message, True)
            print(f'edited rep {payload.message_id}')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.channel_id == self.config.getint('VouchTrackingID'):
            await self._untrack_vouch(payload.message_id, True)
            print(f'deleted vouch {payload.message_id}')
        elif payload.channel_id == self.config.getint('RepTrackingID'):
            await self._untrack_rep(payload.message_id, True)
            print(f'deleted rep {payload.message_id}')

    ###########COMMANDS###########

    @commands.command(aliases=['v', 'vouches'])
    async def get_vouches(self, ctx, member: Member):
        if ctx.message.channel.id != self.config.getint('ControlID') and ctx.message.channel.id != self.config.getint('VouchInfoID'):
            return
        memberinfo = await self._build_vouch_embed(member)
        await ctx.send(embed=memberinfo)
    
    @commands.command(aliases=['rep'])
    async def get_rep(self, ctx, member: Member = None):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            if ctx.message.channel.id != self.config.getint('RepInfoID'):
                return
            else:
                member = None
        if member == None:
            member = ctx.message.author
        memberinfo = await self._build_rep_embed(member)
        await ctx.send(embed=memberinfo)

    @commands.command()
    async def debugprint(self, ctx, member: Member, count: int = 100):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        if member.id in self.data.member_db.keys():
            vouches = self.data.member_db[member.id].vouch_msgs
        else:
            vouches = []
        i = 0
        n = len(vouches) - 1
        vouchtext = ''
        while i < count and n >= 0:
            vouchtext += str(vouches[n]) + '\n'
            i += 1
            n -= 1
        if len(vouchtext) == 0:
            vouchtext = 'no vouches found'
        with open('temp.txt', 'w') as f:
            f.write(vouchtext)
        with open('temp.txt', 'rb') as f:
            await ctx.send(f'Vouch logs for {member.name}:', file=File(f, 'temp.txt'))

    @commands.command()
    @commands.is_owner()
    async def refresh_leaderboard(self, ctx):
        await self.update_leaderboard()

    @commands.command()
    @commands.is_owner()
    async def save_records(self, ctx):
        if ctx.message.channel.id != self.config.getint('ControlID'):
            return
        await self.save()

    @commands.command()
    @commands.is_owner()
    async def echo_records(self, ctx):
        await ctx.channel.send('records ready')