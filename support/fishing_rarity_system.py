import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Base rarity weights (relative, don't need to sum to 100 — random.choices
# normalizes them for you). Higher tier = rarer = lower weight.
# ---------------------------------------------------------------------------
BASE_RARITY_WEIGHTS: dict[str, float] = {
    "COM": 45.0,
    "RAR": 25.0,
    "SR": 15.0,
    "SSR": 8.0,
    "UR": 5.0,
    "LEG": 2.0,
}

# Base chance (0.0 - 1.0) that a cast comes back with absolutely nothing.
BASE_NOTHING_CHANCE = 0.15


@dataclass
class BaitModifier:
    """
    Optional modifier applied when the player used a specific bait item.
    - nothing_chance_delta: added to BASE_NOTHING_CHANCE (can be negative to
      reduce the "nothing" chance — good bait should feel worth buying).
    - tier_weight_multipliers: per-tier multiplier applied AFTER the delta,
      e.g. {"SSR": 2.0, "UR": 1.5} makes rare fish more likely with premium bait.
    """
    nothing_chance_delta: float = 0.0
    tier_weight_multipliers: dict[str, float] = field(default_factory=dict)


# Example bait catalog — wire this up to whatever bait items you sell in shop.py
BAIT_TABLE: dict[str, BaitModifier] = {
    "basic_worm": BaitModifier(nothing_chance_delta=0.0),
    "shiny_lure": BaitModifier(
        nothing_chance_delta=-0.05,
        tier_weight_multipliers={"SSR": 1.5, "UR": 1.5, "LEG": 1.3},
    ),
    "golden_bait": BaitModifier(
        nothing_chance_delta=-0.10,
        tier_weight_multipliers={"SSR": 2.0, "UR": 2.0, "LEG": 1.8},
    ),
}


def _effective_weights(bait: Optional[BaitModifier]) -> dict[str, float]:
    weights = dict(BASE_RARITY_WEIGHTS)
    if bait:
        for tier, mult in bait.tier_weight_multipliers.items():
            if tier in weights:
                weights[tier] *= mult
    return weights


def _effective_nothing_chance(bait: Optional[BaitModifier]) -> float:
    chance = BASE_NOTHING_CHANCE
    if bait:
        chance += bait.nothing_chance_delta
    # clamp so bait can never guarantee a catch or guarantee nothing
    return max(0.02, min(0.75, chance))


def roll_catch(
        fish_table: dict[str, list[dict]],
        bait_id: Optional[str] = None,
) -> Optional[dict]:
    """
    fish_table: dict of rarity_tier -> list of fish dicts, e.g.
        {
            "COM": [{"name": "Cá rô", "emoji": "<:ca_ro:12345>", "value": 10}, ...],
            "RAR": [...],
            "SR": [...],
            "SSR": [...],
            "UR": [...],
            "LEG": [...],
        }
    bait_id: optional key into BAIT_TABLE for the bait the player equipped.

    Returns:
        A fish dict if something was caught, or None if the cast came back empty.
    """
    bait = BAIT_TABLE.get(bait_id) if bait_id else None

    if random.random() < _effective_nothing_chance(bait):
        return None

    weights = _effective_weights(bait)
    # Only consider tiers that actually have fish defined, so an empty tier
    # never gets rolled (which would otherwise force a fallback below).
    available_tiers = [t for t in weights if fish_table.get(t)]
    if not available_tiers:
        return None

    tier = random.choices(
        available_tiers,
        weights=[weights[t] for t in available_tiers],
        k=1,
    )[0]

    return random.choice(fish_table[tier])


def rarity_color(tier: str) -> int:
    """Discord embed color (int) per rarity tier — reuse across fishing + gacha."""
    return {
        "COM": 0x9E9E9E,
        "RAR": 0x4CAF50,
        "SR": 0x2196F3,
        "SSR": 0x9C27B0,
        "UR": 0xFFC107,
        "LEG": 0xFF5252,
    }.get(tier, 0x9E9E9E)