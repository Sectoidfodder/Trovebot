import pickle
from datetime import datetime
from records.records import RecordsData
from records.memberdata import MemberData

class VouchBotData:
    def __init__(self):
        #channel IDs
        self.control_id = -1
        self.tracking_id = -1
        self.tracking_id_rep = -1
        self.warning_id = -1
        self.info_id = -1
        self.info_id_rep = -1
        #message IDs
        self.leadersmsg_alltime = -1
        self.leadersmsg_weekly = -1
        self.leadersmsg_daily = -1
        #dictionary of role ID : number
        self.roles = {}
        self.roles_rep = {}
        #datetime (utc)
        self.timestamp = datetime.min
        #dictionary of user ID : list of (message ID, author ID)
        self.data = {}
        self.data_rep = {}
        self.offsets = {}
    def __setstate__(self, state):
        self.control_id = state.get('control_id', -1)
        self.tracking_id = state.get('tracking_id', -1)
        self.tracking_id_rep = state.get('tracking_id_rep', -1)
        self.info_id = state.get('info_id', -1)
        self.info_id_rep = state.get('info_id_rep', -1)
        self.warning_id = state.get('warning_id', 748532140504907826)
        self.leadersmsg_alltime = state.get('leadersmsg_alltime', -1)
        self.leadersmsg_weekly = state.get('leadersmsg_weekly', -1)
        self.leadersmsg_daily = state.get('leadersmsg_daily', -1)
        self.roles = state.get('roles', {})
        self.roles_rep = state.get('roles_rep', {})
        self.timestamp = state.get('timestamp', datetime.min)
        self.data = state.get('data', {})
        self.data_rep = state.get('data_rep', {})
        self.offsets = state.get('offsets', {})

records = RecordsData()
with open('oldrecords.pickle', 'rb') as f:
    olddata: VouchBotData = pickle.load(f)
    records.timestamp_rep = olddata.timestamp
    records.timestamp_vouch = olddata.timestamp
    print(olddata.timestamp)
    records.roles_vouch = olddata.roles
    records.roles_rep = olddata.roles_rep
    print(len(olddata.data))
    for userid in olddata.data.keys():
        if userid not in records.member_db.keys():
            records.member_db[userid] = MemberData(userid)
        for msg in olddata.data[userid]:
            records.member_db[userid].add_vouch(msg)
    print(len(olddata.data_rep))
    for userid in olddata.data_rep.keys():
        if userid not in records.member_db.keys():
            records.member_db[userid] = MemberData(userid)
        for msg in olddata.data_rep[userid]:
            records.member_db[userid].add_rep(msg)
    print(len(olddata.offsets))
    for userid in olddata.offsets.keys():
        if userid not in records.member_db.keys():
            records.member_db[userid] = MemberData(userid)
        records.member_db[userid].vouch_offset = (0, 0, olddata.offsets[userid])

print(records.member_db[356951866313015298].get_vouch_summary())
print(records.member_db[298228128378126336].get_vouch_summary())
print(records.member_db[519080491572264961].get_vouch_summary())

with open('records.pickle', 'wb') as f:
    pickle.dump(records, f)
