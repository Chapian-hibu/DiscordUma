# seed.py — run once from your project root
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from item_registry import ItemRegistry

MONGO_URI = "mongodb+srv://chapianhieu_db_user:6ScjAYT2omR3MDiG@cluster0.w2auwxv.mongodb.net"
DB_NAME = "umatabase"

async def main():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    registry = ItemRegistry(db)
    await registry.seed_from_json("data/catalog/template_game_items.json")
    print("Seeded. Items:", len(registry._items))
    print("Weights:", registry._rarity_weights)

    #result = await db["items"].delete_many({"rarity_weights": {"$exists": True}})
    #print(result.deleted_count)  # should print 1

    cursor = db["items"].find({})
    docs = await cursor.to_list(length=None)
    for doc in docs:
        if "rarity" not in doc:
            print("MISSING rarity:", doc)






asyncio.run(main())