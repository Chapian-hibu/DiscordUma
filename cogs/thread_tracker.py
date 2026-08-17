"""
Loads the shared gacha item catalog (data/catalog/game_items.json) and
provides lookup, upgrade-chain, and weighted-random-roll helpers for
a future gacha cog to use.\
"""

import json
import os
import random

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(_THIS_DIR, "data", "catalog", "game_items.json")


class ItemRegistry:
    def __init__(self, path: str = CATALOG_PATH):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def reload(self):
        self._data = self._load()

    # --- basic lookups -------------------------------------------------------

    def get_item(self, item_id: str) -> dict | None:
        return self._data["items"].get(item_id)

    def get_items_by_category(self, category: str) -> dict:
        return {
            iid: entry
            for iid, entry in self._data["items"].items()
            if entry["category"] == category
        }

    def get_items_by_rarity(self, rarity: str) -> dict:
        return {
            iid: entry
            for iid, entry in self._data["items"].items()
            if entry["rarity"] == rarity
        }

    def get_items_by_tag(self, tag: str) -> dict:
        return {
            iid: entry
            for iid, entry in self._data["items"].items()
            if tag in entry.get("tags", [])
        }

    # --- upgrade chain helpers -------------------------------------------------

    def get_upgrade_target(self, item_id: str) -> str | None:
        item = self.get_item(item_id)
        if item is None:
            return None
        return item.get("upgrade_to")

    def get_upgrade_source(self, item_id: str) -> str | None:
        item = self.get_item(item_id)
        if item is None:
            return None
        return item.get("upgrade_from")

    def get_full_chain(self, item_id: str) -> list[str]:
        item = self.get_item(item_id)
        if item is None:
            return []

        current = item_id
        while self.get_upgrade_source(current):
            current = self.get_upgrade_source(current)

        chain = [current]
        nxt = self.get_upgrade_target(current)
        while nxt:
            chain.append(nxt)
            nxt = self.get_upgrade_target(nxt)
        return chain

    # --- gacha rolling -------------------------------------------------------

    def roll_rarity(self) -> str:
        weights = self._data["rarity_weights"]
        rarities = list(weights.keys())
        probs = list(weights.values())
        return random.choices(rarities, weights=probs, k=1)[0]

    def roll_item(self, category: str | None = None, rarity: str | None = None, tag: str | None = None) -> tuple[str, dict] | None:
        """
        Roll a single gacha item.
        """
        weights = self._data["rarity_weights"]

        if rarity:
            rarity_attempts = [rarity]
        else:
            rarities = list(weights.keys())
            probs = list(weights.values())
            rarity_attempts = random.choices(rarities, weights=probs, k=len(rarities))
            seen = set()
            rarity_attempts = [r for r in rarity_attempts if not (r in seen or seen.add(r))]
            for r in weights:
                if r not in rarity_attempts:
                    rarity_attempts.append(r)

        for target_rarity in rarity_attempts:
            pool = self.get_items_by_rarity(target_rarity)
            if category:
                pool = {iid: e for iid, e in pool.items() if e["category"] == category}
            if tag:
                pool = {iid: e for iid, e in pool.items() if tag in e.get("tags", [])}
            if pool:
                item_id = random.choice(list(pool.keys()))
                return item_id, pool[item_id]

        return None

registry = ItemRegistry()