"""
item_registry.py

Loads the shared gacha item catalog (data/catalog/game_items.json) and
provides lookup, upgrade-chain, and weighted-random-roll helpers for
a future gacha cog to use.

This catalog is global (shared across all guilds) since it defines
what items exist in the game, not who owns what. Per-user/per-guild
inventory (who has which item, trade history, etc.) should live in a
separate store, the same way EconomySys tracks balances separately
from what currencies exist.
"""

import json
import os
import random

# Resolve relative to this file's own location, not the current working
# directory — so this works correctly whether item_registry.py sits next
# to main.py or inside cogs/, and regardless of where the bot is launched from.
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
        """Re-read the catalog from disk (e.g. after manually editing game_items.json)."""
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

    # --- upgrade chain helpers -------------------------------------------------

    def get_upgrade_target(self, item_id: str) -> str | None:
        """Returns the item_id this item upgrades INTO, or None if max rarity."""
        item = self.get_item(item_id)
        if item is None:
            return None
        return item.get("upgrade_to")

    def get_upgrade_source(self, item_id: str) -> str | None:
        """Returns the item_id this item upgrades FROM, or None if base rarity."""
        item = self.get_item(item_id)
        if item is None:
            return None
        return item.get("upgrade_from")

    def get_full_chain(self, item_id: str) -> list[str]:
        """Returns the full upgrade chain (base -> max) that item_id belongs to."""
        item = self.get_item(item_id)
        if item is None:
            return []

        # walk back to the base of the chain
        current = item_id
        while self.get_upgrade_source(current):
            current = self.get_upgrade_source(current)

        # walk forward collecting the whole chain
        chain = [current]
        nxt = self.get_upgrade_target(current)
        while nxt:
            chain.append(nxt)
            nxt = self.get_upgrade_target(nxt)
        return chain

    # --- gacha rolling -------------------------------------------------------

    def roll_rarity(self) -> str:
        """Weighted-random pick of a rarity tier based on rarity_weights."""
        weights = self._data["rarity_weights"]
        rarities = list(weights.keys())
        probs = list(weights.values())
        return random.choices(rarities, weights=probs, k=1)[0]

    def roll_item(self, category: str | None = None, rarity: str | None = None) -> tuple[str, dict] | None:
        """
        Roll a single gacha item.

        - If rarity is given, rolls only within that rarity.
        - Otherwise rolls a rarity first (weighted via rarity_weights),
          then picks a random item actually at that rarity.
        - If category is given, restricts the pool to that category.

        If the first rolled rarity has no items matching the category
        filter (e.g. a thin/incomplete catalog), this falls back to
        trying every other rarity (best-to-worst weight) before giving
        up, so a gap in one tier doesn't crash the caller.

        Returns (item_id, item_dict), or None only if truly nothing in
        the whole catalog matches the category filter.
        """
        weights = self._data["rarity_weights"]

        if rarity:
            rarity_attempts = [rarity]
        else:
            # weighted order: try the rolled rarity first, then fall back
            # through the rest in weighted-random order (not fixed order,
            # so fallback still roughly respects rarity weighting)
            rarities = list(weights.keys())
            probs = list(weights.values())
            rarity_attempts = random.choices(rarities, weights=probs, k=len(rarities))
            # dedupe while preserving order
            seen = set()
            rarity_attempts = [r for r in rarity_attempts if not (r in seen or seen.add(r))]
            for r in weights:
                if r not in rarity_attempts:
                    rarity_attempts.append(r)

        for target_rarity in rarity_attempts:
            pool = self.get_items_by_rarity(target_rarity)
            if category:
                pool = {iid: e for iid, e in pool.items() if e["category"] == category}
            if pool:
                item_id = random.choice(list(pool.keys()))
                return item_id, pool[item_id]

        return None


# Shared singleton instance other cogs can import directly:
#   from item_registry import registry
registry = ItemRegistry()