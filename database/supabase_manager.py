
import asyncio
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client

class SupabaseManager:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.client: Client = None

    async def initialize(self):
        """Khởi tạo connection Supabase"""
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key are required!")
        
        # Supabase client creation is sync but lightweight (just config)
        self.client = create_client(self.url, self.key)
        
        # Test connection (optional, just to be sure)
        try:
             # Just a lightweight check, e.g. checking auth or a table
             # await self._run_query(lambda: self.client.table('fishing_inventory').select("user_id", count='exact').limit(1).execute())
             pass
        except Exception as e:
            print(f"⚠️ Supabase connection warning: {e}")

    async def _run_query(self, query_func):
        """Helper to run sync Supabase calls in a thread"""
        return await asyncio.to_thread(query_func)

    # ===== GAME STATE METHODS =====

    async def create_game(self, channel_id: int, guild_id: int, language: str, 
                         first_word: str, first_player_id: int, is_bot_challenge: bool = False):
        """Tạo game mới"""
        data = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "language": language,
            "current_word": first_word,
            "current_player_id": first_player_id,
            "used_words": [first_word.lower()],
            "players": [first_player_id],
            "turn_count": 0,
            "is_bot_challenge": is_bot_challenge,
            "turn_start_time": time.time(),
            "wrong_attempts": 0,
            "scores": {},
            # started_at defaults to NOW() in DB
        }
        await self._run_query(lambda: self.client.table('game_states').upsert(data).execute())

    async def get_game_state(self, channel_id: int) -> Optional[Dict]:
        """Lấy trạng thái game hiện tại"""
        response = await self._run_query(lambda: self.client.table('game_states').select("*").eq('channel_id', channel_id).execute())
        
        if not response.data:
            return None
        
        row = response.data[0]
        # Map DB fields back to expected format if needed, but JSON fields come as dicts automatically
        return row

    async def update_game_turn(self, channel_id: int, new_word: str, next_player_id: int):
        """Cập nhật lượt chơi"""
        # Fetch current state to append to lists - simpler in code than complicated SQL/RPC for appending
        # Caution: Race condition possible in high concurrency, but acceptable for turn-based game
        state = await self.get_game_state(channel_id)
        if not state: 
            return

        used_words = state.get('used_words', [])
        used_words.append(new_word.lower())
        
        players = state.get('players', [])
        if next_player_id not in players:
            players.append(next_player_id)
            
        update_data = {
            "current_word": new_word,
            "current_player_id": next_player_id,
            "used_words": used_words,
            "players": players,
            "turn_count": state.get('turn_count', 0) + 1,
            "turn_start_time": time.time(),
            "wrong_attempts": 0
        }
        
        await self._run_query(lambda: self.client.table('game_states').update(update_data).eq('channel_id', channel_id).execute())

    async def update_wrong_attempts(self, channel_id: int, attempts: int):
        await self._run_query(lambda: self.client.table('game_states').update({"wrong_attempts": attempts}).eq('channel_id', channel_id).execute())

    async def update_game_score(self, channel_id: int, player_id: int, points_delta: int):
        state = await self.get_game_state(channel_id)
        if not state: return
        
        scores = state.get('scores', {})
        # JSON keys are strings
        pid_str = str(player_id)
        current = scores.get(pid_str, 0)
        scores[pid_str] = current + points_delta
        
        await self._run_query(lambda: self.client.table('game_states').update({"scores": scores}).eq('channel_id', channel_id).execute())

    async def delete_game(self, channel_id: int):
        await self._run_query(lambda: self.client.table('game_states').delete().eq('channel_id', channel_id).execute())

    async def is_game_active(self, channel_id: int) -> bool:
        response = await self._run_query(lambda: self.client.table('game_states').select("channel_id").eq('channel_id', channel_id).execute())
        return len(response.data) > 0

    # ===== PLAYER STATS METHODS =====

    async def add_points(self, user_id: int, guild_id: int, points: float):
        """Thêm điểm (Global - guild_id=0)"""
        # Using RPC is better for atomic increment, but let's stick to fetch+update or upsert logic
        # Ideally, we create a stored procedure 'increment_points' in supabase, but user has to run SQL.
        # So we'll fetch first. (Atomic increment is hard without RPC)
        
        # Check current points
        # For simplicity and robustness, we treat guild_id=0 as global
        
        # Try to get existing
        res = await self._run_query(lambda: self.client.table('player_stats').select("total_points").eq('user_id', user_id).eq('guild_id', 0).execute())
        
        current_points = 0
        if res.data:
            current_points = res.data[0].get('total_points', 0)
            
        new_total = current_points + points
        
        data = {
            "user_id": user_id,
            "guild_id": 0,
            "total_points": new_total
        }
        # Upsert effectively
        await self._run_query(lambda: self.client.table('player_stats').upsert(data).execute())

    async def update_player_stats(self, user_id: int, guild_id: int, word: str, is_correct: bool):
        """Cập nhật thống kê"""
        # Fetch current
        res = await self._run_query(lambda: self.client.table('player_stats').select("*").eq('user_id', user_id).eq('guild_id', guild_id).execute())
        
        stats = {}
        if res.data:
            stats = res.data[0]
        else:
            stats = {
                "user_id": user_id, 
                "guild_id": guild_id, 
                "words_submitted": 0, 
                "correct_words": 0, 
                "wrong_words": 0,
                "longest_word": "",
                "longest_word_length": 0
            }
        
        stats["words_submitted"] = stats.get("words_submitted", 0) + 1
        stats["last_played"] = datetime.now().isoformat()
        
        if is_correct:
            stats["correct_words"] = stats.get("correct_words", 0) + 1
            w_len = len(word)
            if w_len > stats.get("longest_word_length", 0):
                stats["longest_word"] = word
                stats["longest_word_length"] = w_len
        else:
            stats["wrong_words"] = stats.get("wrong_words", 0) + 1
            
        await self._run_query(lambda: self.client.table('player_stats').upsert(stats).execute())

    async def get_player_points(self, user_id: int, guild_id: int) -> float:
        res = await self._run_query(lambda: self.client.table('player_stats').select("total_points").eq('user_id', user_id).eq('guild_id', 0).execute())
        if res.data:
            return res.data[0].get('total_points', 0)
        return 0

    async def transfer_points(self, from_user_id: int, to_user_id: int, amount: float) -> bool:
        if amount <= 0: return False
        
        # Transaction-like sequence (Supabase REST API doesn't support transactions unless via RPC)
        # 1. Check sender balance
        sender_bal = await self.get_player_points(from_user_id, 0)
        if sender_bal < amount:
            return False
            
        # 2. Subtract from sender
        await self.add_points(from_user_id, 0, -amount)
        
        # 3. Add to receiver
        await self.add_points(to_user_id, 0, amount)
        
        return True

    async def get_leaderboard(self, member_ids: List[int], limit: int = 10) -> List[Dict]:
        if not member_ids: return []
        
        # Supabase 'in' filter takes a list
        # We need to filter by user_id in member_ids AND guild_id=0
        
        # Note: If member_ids is HUGE, this might fail URL length limits. 
        # But usually in a guild context 10-100 top users is fine, fetching all might be needed for large guilds.
        # Fallback: Fetch top globally and filter.
        
        res = await self._run_query(lambda: self.client.table('player_stats')
            .select("user_id, total_points, games_played, correct_words, longest_word")
            .eq('guild_id', 0)
            .order('total_points', desc=True)
            .limit(1000) # Get top 1000 globally to increase hit rate
            .execute())
            
        global_top = res.data
        
        # Filter intersection with member_ids
        member_set = set(member_ids)
        local_top = []
        
        for row in global_top:
            if row['user_id'] in member_set:
                local_top.append(row)
                if len(local_top) >= limit:
                    break
        
        return local_top

    # ===== GAME HISTORY METHODS =====
    
    async def save_game_history(self, channel_id: int, guild_id: int, 
                                language: str, winner_id: Optional[int], 
                                total_turns: int, total_words: int, started_at: str):
        data = {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "language": language,
            "winner_id": winner_id,
            "total_turns": total_turns,
            "total_words": total_words,
            "started_at": started_at,
            "ended_at": datetime.now().isoformat()
        }
        await self._run_query(lambda: self.client.table('game_history').insert(data).execute())

    # ===== CHANNEL CONFIG METHODS =====
    
    async def set_channel_config(self, channel_id: int, guild_id: int, game_type: str):
        data = {"channel_id": channel_id, "guild_id": guild_id, "game_type": game_type}
        await self._run_query(lambda: self.client.table('channel_configs').upsert(data).execute())

    async def get_channel_config(self, channel_id: int) -> Optional[str]:
        res = await self._run_query(lambda: self.client.table('channel_configs').select("game_type").eq('channel_id', channel_id).execute())
        if res.data:
            return res.data[0].get('game_type')
        return None

    # ===== AGGREGATE STATS METHODS =====

    async def get_player_stats(self, user_id: int, guild_id: int) -> Optional[Dict]:
        # 1. Global stats
        res_global = await self._run_query(lambda: self.client.table('player_stats')
            .select("total_points, daily_streak")
            .eq('user_id', user_id)
            .eq('guild_id', 0)
            .execute())
            
        total_points = 0
        daily_streak = 0
        if res_global.data:
            total_points = res_global.data[0].get('total_points', 0)
            daily_streak = res_global.data[0].get('daily_streak', 0)
            
        # 2. Local stats
        res_local = await self._run_query(lambda: self.client.table('player_stats')
            .select("games_played, words_submitted, correct_words, wrong_words, longest_word, longest_word_length")
            .eq('user_id', user_id)
            .eq('guild_id', guild_id)
            .execute())
            
        if not res_local.data and total_points == 0:
            return None
            
        stats = {
            'total_points': total_points,
            'daily_streak': daily_streak,
            'games_played': 0,
            'words_submitted': 0,
            'correct_words': 0,
            'wrong_words': 0,
            'longest_word': "",
            'longest_word_length': 0
        }
        
        if res_local.data:
            stats.update(res_local.data[0])
            
        return stats

    # ===== DAILY METHODS =====
    
    async def get_daily_info(self, user_id: int):
        res = await self._run_query(lambda: self.client.table('player_stats')
            .select("last_daily_claim, daily_streak, last_daily_reward")
            .eq('user_id', user_id)
            .eq('guild_id', 0)
            .execute())
            
        if res.data:
            # Need to figure out return format matching original DB manager
            # Tuple: (last_daily_claim, daily_streak, last_daily_reward)
            # Timestamps in supabase are ISO strings usually
            r = res.data[0]
            return (r.get('last_daily_claim'), r.get('daily_streak', 0), r.get('last_daily_reward', 0))
        return (None, 0, 0)
        
    async def update_daily(self, user_id: int, reward: float, streak: int):
        # Fetch current points to add
        current = await self.get_player_points(user_id, 0)
        new_total = current + reward
        
        data = {
            "user_id": user_id,
            "guild_id": 0,
            "last_daily_claim": datetime.now().isoformat(),
            "daily_streak": streak,
            "last_daily_reward": reward,
            "total_points": new_total
        }
        await self._run_query(lambda: self.client.table('player_stats').upsert(data).execute())

    # ===== FISHING GAME METHODS =====

    async def get_fishing_data(self, user_id: int) -> Dict:
        res = await self._run_query(lambda: self.client.table('fishing_inventory').select("*").eq('user_id', user_id).execute())
        
        default_data = {
            'rod_type': 'Plastic Rod',
            'boat_type': 'None',
            'inventory': {'fish': {}, 'baits': {}},
            'upgrades': {},
            'stats': {
                'xp': 0, 
                'level': 1, 
                'money': 0,
                'current_biome': 'Lake',
                'unlocked_biomes': ['Lake'],
                'current_bait': None
            },
            'last_fished': None
        }

        if not res.data:
            return default_data

        row = res.data[0]
        # JSON fields are already dicts
        # Ensure keys exist
        inv = row.get('inventory') or {}
        if 'fish' not in inv: inv = {'fish': {}, 'baits': {}}
        
        st = row.get('stats') or {}
        if 'current_biome' not in st: st['current_biome'] = 'Lake'
        if 'unlocked_biomes' not in st: st['unlocked_biomes'] = ['Lake']
        
        return {
            'rod_type': row.get('rod_type', 'Plastic Rod'),
            'boat_type': row.get('boat_type', 'None'),
            'inventory': inv,
            'upgrades': row.get('upgrades') or {},
            'stats': st,
            'last_fished': row.get('last_fished')
        }

    async def update_fishing_data(self, user_id: int, rod_type: str = None, boat_type: str = None, 
                                  inventory: Dict = None, upgrades: Dict = None, stats: Dict = None):
        
        # To update partially, we first need to know if the row exists, but upsert handles logic 
        # IF we provide all fields. Supabase partial update via .update() only works if row exists.
        # But here we might be creating new user.
        # So we should probably fetch first (costly) or use upsert with all previous data.
        
        # We need to fetch current data to merge anyway! 
        # The caller (cog) usually fetches, modifies, passes back. 
        # But wait, the arguments allow None. So we must fetch here if any arg is None.
        
        current = await self.get_fishing_data(user_id)
        
        data = {
            "user_id": user_id,
            "rod_type": rod_type if rod_type is not None else current['rod_type'],
            "boat_type": boat_type if boat_type is not None else current['boat_type'],
            "inventory": inventory if inventory is not None else current['inventory'],
            "upgrades": upgrades if upgrades is not None else current['upgrades'],
            "stats": stats if stats is not None else current['stats'],
            "last_fished": datetime.now().isoformat()
        }
        
        await self._run_query(lambda: self.client.table('fishing_inventory').upsert(data).execute())
        
    async def get_fishing_rank(self, user_id: int) -> int:
        # Complex query logic for ranking.
        # We need to rank by stats->level (desc), then stats->xp (desc).
        # This is hard to do efficiently with JSON columns without generated columns in Postgres.
        # But we can just fetch all (if not too many users) or try to use postgres JSON operators if client allows?
        
        # Efficient approach: Fetch specific columns for all users and sort in python.
        # Not scalable for millions, but fine for thousands.
        
        res = await self._run_query(lambda: self.client.table('fishing_inventory').select("user_id, stats").execute())
        
        if not res.data: return 1
        
        # Parse and sort
        data = []
        for r in res.data:
            s = r.get('stats', {})
            data.append((r['user_id'], s.get('level', 1), s.get('xp', 0)))
            
        data.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        for idx, item in enumerate(data):
            if item[0] == user_id:
                return idx + 1
        return len(data) + 1

    async def update_game_players(self, channel_id: int, players: List[int], turn_start_time: float):
        """Cập nhật danh sách người chơi và thời gian bắt đầu lượt"""
        data = {
            "players": players,
            "turn_start_time": turn_start_time
        }
        await self._run_query(lambda: self.client.table('game_states').update(data).eq('channel_id', channel_id).execute())

    async def add_player_to_game(self, channel_id: int, player_id: int):
        """Thêm người chơi vào game (dùng cho Bot Challenge)"""
        state = await self.get_game_state(channel_id)
        if not state: return
        
        players = state.get('players', [])
        if player_id not in players:
            players.append(player_id)
            await self._run_query(lambda: self.client.table('game_states').update({"players": players}).eq('channel_id', channel_id).execute())

    # ===== ADMIN METHODS =====

    async def reset_player_stats(self, user_id: int, guild_id: int):
        """Reset stats của một user (giữ lại points)"""
        # 1. Clear fishing inventory
        await self._run_query(lambda: self.client.table('fishing_inventory').delete().eq('user_id', user_id).execute())
        
        # 2. Reset Local Stats (delete row or zero out)
        # Deleting row is cleaner
        await self._run_query(lambda: self.client.table('player_stats').delete().eq('user_id', user_id).eq('guild_id', guild_id).execute())
        
        # 3. Reset Global Stats (except points) in user_id, guild_id=0
        data = {
            "games_played": 0, "words_submitted": 0, "correct_words": 0, "wrong_words": 0,
            "longest_word": "", "longest_word_length": 0,
            "daily_streak": 0, "last_daily_claim": None, "last_daily_reward": 0
        }
        await self._run_query(lambda: self.client.table('player_stats').update(data).eq('user_id', user_id).eq('guild_id', 0).execute())

    async def reset_all_stats(self, guild_id: int):
        """Reset stats toàn server (giữ points)"""
        # 1. Clear all fishing inventories? (Dangerous global action)
        # Code requested: "DELETE FROM fishing_inventory"
        await self._run_query(lambda: self.client.table('fishing_inventory').delete().neq('user_id', 0).execute()) # Hack to delete all
        
        # 2. Delete all local stats for this guild
        await self._run_query(lambda: self.client.table('player_stats').delete().eq('guild_id', guild_id).execute())
        
        # 3. Reset global stats for ALL (except points)
        data = {
            "games_played": 0, "words_submitted": 0, "correct_words": 0, "wrong_words": 0,
            "longest_word": "", "longest_word_length": 0,
            "daily_streak": 0, "last_daily_claim": None, "last_daily_reward": 0
        }
        # In supabase-py, update typically updates all matching rows. 
        # But we must be careful. neq('user_id', 0) selects all valid users roughly.
        await self._run_query(lambda: self.client.table('player_stats').update(data).eq('guild_id', 0).execute())

    async def reset_player_coiz(self, user_id: int):
        """Reset coiz về 0"""
        await self._run_query(lambda: self.client.table('player_stats').update({"total_points": 0}).eq('user_id', user_id).eq('guild_id', 0).execute())

    async def reset_all_coiz(self):
        """Reset toàn bộ coiz về 0"""
        await self._run_query(lambda: self.client.table('player_stats').update({"total_points": 0}).eq('guild_id', 0).execute())
