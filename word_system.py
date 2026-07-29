import re
import time
from collections import Counter

import discord


class CountSession:
    def __init__(self):
        self.active = False
        self.users = {}
        self.total_letters = 0
        self.total_words = 0
        self.word_counts = Counter()
        self.started_at = None
        self.timer_task = None
        self.backfill_cancelled = False


class WordStats:
    def __init__(self):
        self.sessions = {}

    def _get_session(self, channel_id) -> CountSession:
        if channel_id not in self.sessions:
            self.sessions[channel_id] = CountSession()
        return self.sessions[channel_id]

    def is_active(self, channel_id) -> bool:
        return self._get_session(channel_id).active

    def start(self, channel_id) -> CountSession:
        session = self._get_session(channel_id)
        session.active = True
        session.users = {}
        session.total_letters = 0
        session.total_words = 0
        session.word_counts = Counter()
        session.backfill_cancelled = False
        session.started_at = time.time()
        return session

    def stop(self, channel_id) -> CountSession:
        session = self._get_session(channel_id)
        session.active = False
        if session.timer_task and not session.timer_task.done():
            session.timer_task.cancel()
        return session

    @staticmethod
    def count_letters(text: str) -> int:
        return sum(1 for ch in text if ch.isalpha())

    @staticmethod
    def count_words(text: str) -> int:
        return sum(1 for token in text.split() if any(ch.isalpha() for ch in token))

    @staticmethod
    def clean_words(token: str)-> str:
        return re.sub(r"[^a-z]", " ", token.lower())

    @staticmethod
    def extract_words(content: str) -> list[str]:
        raw_tokens = content.split()
        cleaned = (WordStats.clean_word(tok) for tok in raw_tokens)
        return [w for w in cleaned if w]

    def record_message(self, channel_id, user_id, user_name, content: str):
        session = self._get_session(channel_id)
        if not session.active:
            return

        letters = self.count_letters(content)
        words = self.count_words(content)
        if letters == 0 and words == 0:
            return

        user_id = str(user_id)
        if user_id not in session.users:
            session.users[user_id] = {"letters": 0, "words": 0, "name": user_name}

        session.users[user_id]["letters"] += letters
        session.users[user_id]["words"] += words
        session.total_letters += letters
        session.total_words += words

    def build_report(self, channel_id) -> str:
        session = self._get_session(channel_id)
        if not session.users:
            return "No countable messages were sent during this session"

        ranked = sorted(
            session.users.items(),
            key=lambda kv: kv[1]["words"],
            reverse=True
        )

        lines = ["**Results**\n"]
        for _, data in ranked:
            lines.append(f"- **{data['name']}**: {data['letters']} letters, {data['words']} words")

        lines.append(f"\n**Total:** {session.total_letters} letters, {session.total_words} words")
        return "\n".join(lines)

    def get_word_counts(self, channel_id) -> Counter:
        return Counter(self._get_session(channel_id).word_counts)

    def get_user_word_counts(self, channel_id, user_id) -> Counter:
        session = self._get_session(channel_id)
        user = session.users.get(str(user_id))
        return Counter(user["word_counts"]) if user else Counter()

    def get_unique_words(self, channel_id) -> list[str]:
        return list(self._get_session(channel_id).word_counts.keys())

class ConfirmView(discord.ui.View):
    def __init__(self,author_id,timeout:float = 30):
        super().__init__(timeout= timeout)
        self.author_id = author_id
        self.value = None
        #True = confirm
        #False = cancel-led
        #None = Timed out
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This confirmation isn't for you dumbass", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, Count 'em", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message("Starting the count..",view = None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message("Cancelled the count..",view = None)
        self.stop()
