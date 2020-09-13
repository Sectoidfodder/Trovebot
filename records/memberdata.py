import pickle
import bisect
from utils import snowflake
from typing import Tuple, List, Dict, Optional

#(message id, author id, mention count)
Msg = Tuple[int, int, int]
#(unique users, session count, total vouches)
Summary = Tuple[int, int, int]

class MemberData():
    #messages within n seconds count as same crafting session
    _SESSION_DURATION = 60

    #user snowflake
    id: int
    #sorted list of current league vouches
    vouch_msgs: List[Msg]
    #old vouch data, league : summary
    vouch_history: Dict[str, Summary]
    #manual stat offsets
    vouch_offset: Summary
    #permanent leaderboard roles from old leagues
    legacy_roles: List[int]
    #sorted list of all rep messages
    rep_msgs: List[Msg]

    def __init__(self, id: int):
        self.id = id
        self.vouch_msgs = []
        self.vouch_history = {}
        self.vouch_offset = (0, 0, 0)
        self.legacy_roles = []
        self.rep_msgs = []

    #adds message to a list, maintaining sorted order and ignoring duplicate IDs
    def _add_msg(self, msg: Msg, msglist: List[Msg]):
        dummy = (msg[0], 0, 0)
        n = bisect.bisect_left(msglist, dummy)
        if n >= len(msglist) or msglist[n][0] != msg[0]:
            msglist.insert(n, msg)
        else:
            pass
            #print(f'Repeat msg ID ignored: {msg[0]}')

    def add_vouch(self, msg: Msg):
        self._add_msg(msg, self.vouch_msgs)
    
    def add_rep(self, msg: Msg):
        self._add_msg(msg, self.rep_msgs)

    #removes message from a sorted list by message id, return it if it exist or None otherwise
    def _remove_msg(self, msgid: int, msglist: List[Msg]) -> Optional[Msg]:
        dummy = (msgid, 0, 0)
        n = bisect.bisect_left(msglist, dummy)
        if n < len(msglist) and msglist[n][0] == msgid:
            return msglist.pop(n)
        return None
    
    def remove_vouch(self, msgid: int) -> Optional[Msg]:
        return self._remove_msg(msgid, self.vouch_msgs)

    def remove_rep(self, msgid: int) -> Optional[Msg]:
        return self._remove_msg(msgid, self.rep_msgs)

    #returns (unique, session, total) from a list of (message id, author id, mention count)
    def _get_summary(self, msglist: List[Msg]) -> Summary:
        sessions = 0
        prevsession = None
        authors = set()
        total = 0
        for (msgid, authorid, msgcount) in msglist:
            authors.add(authorid)
            total += msgcount
            if prevsession == None or snowflake.time_diff(prevsession, msgid) > self._SESSION_DURATION:
                sessions += 1
            prevsession = msgid
        return (len(authors), sessions, total)
    
    def get_vouch_summary(self) -> Summary:
        summary = self._get_summary(self.vouch_msgs)
        total = max(0, summary[2] - self.vouch_offset[2])
        session = max(0, min(total, summary[1] - self.vouch_offset[1]))
        unique = max(0, min(session, summary[0] - self.vouch_offset[0]))
        return (unique, session, total)

    def get_vouch_history(self) -> Summary:
        totals = tuple(map(sum, zip(*self.vouch_history.values())))
        if len(totals) < 3:
            return (0, 0, 0)
        else:
            return totals

    def get_rep_summary(self) -> Summary:
        return self._get_summary(self.rep_msgs)

    #retrieves the most recent message IDs from a list, in reverse chronological order
    def _get_recent(self, msglist: List[Msg], count: int) -> List[int]:
        if count >= len(msglist):
            return [m for m, a, n in msglist[::-1]]
        else:
            return [m for m, a, n in msglist[:len(msglist)-count-1:-1]]

    def get_recent_vouches(self, count: int) -> List[int]:
        return self._get_recent(self.vouch_msgs, count)

    def get_recent_rep(self, count: int) -> List[int]:
        return self._get_recent(self.rep_msgs, count)