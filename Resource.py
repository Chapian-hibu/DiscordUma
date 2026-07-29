# Resource.py
import json
import os
import random


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
            self.balances[user_id] = self._default_record()
            return

        if not isinstance(self.balances[user_id], dict):
            old_balance = self.balances[user_id]
            self.balances[user_id] = self._default_record()
            self.balances[user_id]["balance"] = old_balance
            return
        defaults = self._default_record()
        for key, default_value in defaults.items():
            if key not in self.balances[user_id]:
                self.balances[user_id][key] = default_value

    @staticmethod
    def _default_record():
        """Full default shape for a new user record"""
        return {
            "balance": 0,
            "last_daily": None,
            "Spd": 0,
            "Stm": 0,
            "Pow": 0,
            "Gut": 0,
            "Wis": 0,
            "s_point":0,
            "rank": "Unrated",
            "collectibles" : {}
        }

    def set_field(self,user_id, field, value):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field] = value
        self.save_data()

    def increment_field(self, user_id, field, amount = 0):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field] = self.balances[user_id].get(field,0) + amount
        self.save_data()
        return self.balances[user_id][field]

    def get_field(self, user_id, field):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id].get(field,-1)


    def decrement_field(self, user_id, field,amount):
        #remove amount from a field (mostly cash)
        field_type = field
        user_id = str(user_id)
        self.ensure_user(user_id)
        current_balance = self.balances[user_id][field_type]

        if current_balance < amount:
            return {"success": False, "message": "Insufficient amount"}

        self.balances[user_id][field_type] = current_balance - amount
        self.save_data()
        return {"success": True, "new_balance": self.balances[user_id][field_type]}

    def index_field(self, from_user_id, to_user_id,field, amount):
        field_type = field
        #Moving money
        removal = self.decrement_field(from_user_id, field_type, amount)

        if not removal["success"]:
            return removal

        self.increment_field(to_user_id,field_type,amount)
        return {"success": True, "message": "Transfer completed"}


    def set_money(self, user_id, amount):
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

    """-----------------------TIME INTERVAL-----------------------"""
    def get_last_cd(self, user_id):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["last_daily"]

    def set_last_cd(self,user_id,timestamp_iso):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id]["last_daily"] = timestamp_iso
        self.save_data()

    """-----------------------COLLECTABLES-----------------------"""
    def add_collectible(self, user_id, item_id,quantity =1):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current = self.balances[user_id]["collectibles"]. get(item_id,0)
        self.balances[user_id]["collectibles"][item_id] = current+quantity
        self.save_data()
        return self.balances[user_id]["collectibles"][item_id]

    def remove_collectible(self, user_id, item_id,quantity = 1):
        """Remove item, return False if not enough owned"""
        user_id = str(user_id)
        self.ensure_user(user_id)
        current = self.balances[user_id]["collectibles"]. get(item_id,0)

        if current < quantity:
            return{"success": False, "message": "Chưa đủ tài sản"}

        new_amount = current - quantity
        if new_amount == 0:
            del self.balances[user_id]["collectibles"][item_id]
        else:
            self.balances[user_id]["collectibles"][item_id] = new_amount

        self.save_data()
        return {"success": True}

    def get_collectible(self, item_id):
        user_id = str(item_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["collectibles"]

    def has_collectible(self, user_id, item_id, quantity = 1):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["collectibles"].get(item_id,0) >= quantity

    """-----------------------RNG STUFF-----------------------"""
    @staticmethod
    def default_train_type():
        weighted_lobby = {'Spd':[0.8,0,0.4,0,0,2],
                          'Stm':[0,0.7,0,0.3,0,2],
                          'Pow':[0,0.4,0.6,0,0,2],
                          'Gut':[0.3,0,0.3,0.6,0,2],
                          'Wis':[0,0,0.2,0,0.6,2]}
        t_type = random.choice(list(weighted_lobby.keys()))
        t_value = weighted_lobby[t_type]
        return t_type, t_value

    @staticmethod
    def default_train_value():
        return random.randint(1,19)

    @staticmethod
    def default_fail_value(value):
        value_v = value
        new_value = round(value_v/2 * 10)
        return new_value




