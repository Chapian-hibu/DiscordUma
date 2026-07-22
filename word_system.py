#import asyncio
import time

class CountSession:
    #Start Counting since the comment, in this channel

    def __init__(self):
        self.active = False
        self.users = {} #user_id -> {"letters": int, "words":int,"name": str}
        self.total_letter = 0
        self.total_words = 0
        self.started_at = None
        self.timer_task = None

class WordStats:
    def __init__(self):
        self.sessions = {}

    def _get_session(self, channel_id):
        channel = str(channel_id)
        if channel not in self.sessions:
            self.sessions[channel_id] = CountSession()
        return self.sessions[channel_id]

    def is_active(self, channel_id):
        return self._get_session(channel_id).active

    def start(self, channel_id) -> CountSession:
        session = self._get_session(channel_id)
        session.active = True
        session.started_at = time.time().users = {}
        session.total_letters = 0
        session.total_words = 0
        session.started_at = time.time()
        return session

    def stop(self, channel_id) -> CountSession:
        session = self._get_session(channel_id)
        session.active = False
        if session.timer_task and not session.timer_task.done():
            session.timer_task.cancel()
        return session

    @staticmethod
    def count_letters(text:str) -> int:
        return sum(1 for ch in text if ch.isalpha())

    @staticmethod
    def count_words(text:str) -> int:
        return sum(1 for token in text.split() if any(ch.isalpha() for ch in token))

    def record_message(self,channel_id,user_id,user_name,content:str):
        session = self._get_session(channel_id)
        if not session.active:
            return

        letters = self.count_letters(content)
        words = self.count_words(content)
        if letters == 0 and words == 0:
            return

        user_id = str(user_id)
        if user_id not in session.users:
            session.users[user_id] = {"letters":0,"words":0,"name": user_name}

        session.users[user_id]["letters"] += letters
        session.users[user_id]["words"] += words
        session.total_letters += letters
        session.total_words += words

    def build_report(self,channel_id) -> str:
        session = self._get_session(channel_id)
        if not session.users:
            return "No countable messages were sent during this session"

        ranked = sorted(
            session.users.items(),
            key=lambda kv: kv[1]["words"],
            reverse=True
        )

        lines = ["**📊 Count Session Results**\n"]
        for _, data in ranked:
            lines.append(f"- **{data['name']}**: {data['letters']} letters, {data['words']} words")

        lines.append(f"\n**Total (thread):** {session.total_letters} letters, {session.total_words} words")
        return "\n".join(lines)