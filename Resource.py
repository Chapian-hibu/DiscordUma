# Resource.py
import json
import os


class EconomySys:
    def __init__(self, data_file='economy_data.json'):
        self.data_file = data_file
        self.balances = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.balances, f, indent=4)

    def ensure_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.balances:
            self.balances[user_id] = {"balance": 0, "last_daily": None}
        elif not isinstance(self.balances[user_id], dict):
            old_balance = self.balances[user_id]
            self.balances[user_id] = {"balance": old_balance, "last_daily": None}

    def get_balance(self, user_id):
        """Get user's  balance"""
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["balance"]

    def add_money(self, user_id, amount):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id]["balance"] += amount
        self.save_data()
        return self.balances[user_id]["balance"]

    def remove_money(self, user_id, amount):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current_balance = self.balances[user_id]["balance"]

        if current_balance < amount:
            return {"success": False, "message": "Insufficient funds"}

        self.balances[user_id]["balance"] = current_balance - amount
        self.save_data()
        return {"success": True, "new_balance": self.balances[user_id]["balance"]}

    def transfer_money(self, from_user_id, to_user_id, amount):
        #Moving money
        removal = self.remove_money(from_user_id, amount)

        if not removal["success"]:
            return removal

        self.add_money(to_user_id, amount)
        return {"success": True, "message": "Transfer completed"}

    def set_balance(self, user_id, amount):
        """Set user's balance (admin function)"""
        user_id = str(user_id)
        self.balances[user_id]["balance"] = amount
        self.save_data()
        return amount

    def leaderboard(self, limit=10):
        #Leader board of Economy
        sorted_users = sorted(self.balances.items(),
                              key=lambda x: x[1]["balance"] if isinstance(x[1], dict ) else x[1],
                              reverse=True)
        return sorted_users[:limit]

    def get_last_cd(self, user_id):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["last_daily"]

    def set_last_cd(self,user_id,timestamp_iso):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id]["last_daily"] = timestamp_iso
        self.save_data()


