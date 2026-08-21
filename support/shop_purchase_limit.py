"""
support/shop_purchase_limit.py

Two scarcity rules layered on top of ShopStore's flat `stock: list[str]`:

  1. PER-USER LIMIT: a user may buy a given item_id at most once per
     rotation. Scoped by `last_reroll` (already on the shop doc), so a
     fresh reroll = a fresh slate automatically, no extra bookkeeping.

  2. GLOBAL STOCK: since `stock` is a flat list (e.g. ["potion", "potion",
     "sword"]), an item's available quantity is just how many times its
     id appears. Buying removes ONE occurrence -- decrementing supply
     without touching other items' counts.

`attempt_purchase()` is the single entry point shop_buy() should call.
It records the purchase, reserves stock, and checks balance -- rolling
back cleanly at whichever step fails, so nobody loses carat for an item
they didn't get, and nobody gets locked out by a failed attempt.
"""

from dataclasses import dataclass


@dataclass
class PurchaseResult:
    success: bool
    reason: str = ""  # "already_owned" | "out_of_stock" | "insufficient_funds" | ""

    def __bool__(self) -> bool:
        return self.success


async def attempt_purchase(shop_store, economy, user_id: int, item_id: str, price: int) -> PurchaseResult:
    # --- Step 1: per-user-per-rotation check + reservation -----------------
    # record_purchase() uses a unique index under the hood, so even two
    # simultaneous /shop buy calls from the same user can't both succeed.
    if await shop_store.has_purchased(user_id, item_id):
        return PurchaseResult(False, "already_owned")

    recorded = await shop_store.record_purchase(user_id, item_id)
    if not recorded:
        # Lost a race against another click from the same user.
        return PurchaseResult(False, "already_owned")

    # --- Step 2: reserve one unit of global stock ---------------------------
    reserved = await shop_store.reserve_stock(item_id)
    if not reserved:
        await shop_store.unrecord_purchase(user_id, item_id)
        return PurchaseResult(False, "out_of_stock")

    # --- Step 3: balance check ------------------------------------------------
    balance = await economy.get_field(user_id, "carat")
    if balance < price:
        await shop_store.release_stock(item_id)
        await shop_store.unrecord_purchase(user_id, item_id)
        return PurchaseResult(False, "insufficient_funds")

    await economy.decrement_field(user_id, "carat", price)
    return PurchaseResult(True)