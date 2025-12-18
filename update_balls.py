
import asyncio
import json
import os
import config
from database.supabase_manager import SupabaseManager

USER_ID = 561443914062757908

async def main():
    if config.SUPABASE_URL and config.SUPABASE_KEY:
        print(f"Detected Supabase URL. Connecting...")
        db = SupabaseManager(config.SUPABASE_URL, config.SUPABASE_KEY)
        await db.initialize()
        
        try:
            print(f"Fetching data for user {USER_ID}...")
            data = await db.get_fishing_data(USER_ID)
            inventory = data.get("inventory", {})
            print(f"Current inventory fetched.")
            
            # Update Dragon Balls
            inventory["dragon_balls"] = [1, 2, 3, 4, 5, 6, 7]
            print(f"Added 7 Dragon Balls to inventory.")
            
            # Save back
            await db.update_fishing_data(USER_ID, inventory=inventory)
            print("[SUCCESS] Supabase updated successfully!")
            
        except Exception as e:
            print(f"[ERROR] Error updating Supabase: {e}")
    else:
        print("No Supabase Credentials found. Checking SQLite...")
        # Fallback to SQLite (reusing previous logic just in case)
        import sqlite3
        DB_PATH = config.DATABASE_PATH
        
        if not os.path.exists(DB_PATH):
             print(f"[ERROR] Database file not found at {DB_PATH}")
             return

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT inventory FROM fishing_inventory WHERE user_id = ?", (USER_ID,))
            row = cursor.fetchone()
            if row:
                inventory = json.loads(row[0])
                inventory["dragon_balls"] = [1, 2, 3, 4, 5, 6, 7]
                new_inv_json = json.dumps(inventory)
                cursor.execute("UPDATE fishing_inventory SET inventory = ? WHERE user_id = ?", (new_inv_json, USER_ID))
                conn.commit()
                print("[SUCCESS] SQLite database updated successfully.")
            else:
                print(f"User {USER_ID} not found in SQLite.")
            conn.close()
        except Exception as e:
            print(f"[ERROR] Error updating SQLite: {e}")

if __name__ == "__main__":
    asyncio.run(main())
