"""
Leaderboard Cog - Bảng xếp hạng và thống kê
"""
import discord
from discord.ext import commands
from discord import app_commands

import config
from utils import embeds, emojis



class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db):
        self.bot = bot
        self.db = db
    
    @app_commands.command(name="leaderboard", description="🏆 Xem bảng xếp hạng server")
    async def leaderboard(self, interaction: discord.Interaction):
        """Hiển thị top 10 người chơi trong server này"""
        # Get list of member IDs in the current guild
        if not interaction.guild:
            await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong server!", ephemeral=True)
            return
            
        # Collect member IDs. Note: this relies on intents.members being enabled and cache populated.
        member_ids = [member.id for member in interaction.guild.members]
        
        # Lấy dữ liệu leaderboard
        leaderboard_data = await self.db.get_leaderboard(member_ids=member_ids, limit=10)
        
        # Tạo embed
        embed = embeds.create_leaderboard_embed(
            leaderboard_data=leaderboard_data,
            server_name=interaction.guild.name
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="stats", description="📊 Xem hồ sơ và thống kê tổng hợp của người chơi")
    @app_commands.describe(user="Người chơi cần xem (để trống để xem của bạn)")
    async def stats(self, interaction: discord.Interaction, user: discord.User = None):
        """Hiển thị thống kê tổng hợp của người chơi (Tất cả các game)"""
        target_user = user or interaction.user
        
        # 1. Fetch General & Word Game Stats
        stats = await self.db.get_player_stats(target_user.id, interaction.guild_id)
        if not stats:
            # If no legacy stats but maybe has fishing stats? 
            # We initialize default "empty" stats to allow showing fishing profile if exists.
            stats = {
                'total_points': await self.db.get_player_points(target_user.id, interaction.guild_id),
                'games_played': 0, 'words_submitted': 0, 'correct_words': 0, 'wrong_words': 0,
                'longest_word': "", 'longest_word_length': 0, 'daily_streak': 0
            }

        # 2. Fetch Fishing Stats
        fishing_data = await self.db.get_fishing_data(target_user.id)
        fishing_stats = fishing_data.get("stats", {})
        fishing_rank = await self.db.get_fishing_rank(target_user.id)
        
        # --- PREPARE DATA ---
        
        # General
        total_points = stats['total_points']
        daily_streak = stats.get('daily_streak', 0)
        
        # Word Game
        w_played = stats['games_played']
        w_correct = stats['correct_words']
        w_accuracy = (w_correct / stats['words_submitted'] * 100) if stats['words_submitted'] > 0 else 0
        w_longest = stats['longest_word'].upper() if stats['longest_word'] else "Chưa có"
        
        # Fishing
        f_level = fishing_stats.get("level", 1)
        f_xp = fishing_stats.get("xp", 0)
        f_next_xp = int(1000 * (1.5 ** (f_level - 1)))
        f_rod = fishing_data.get("rod_type", "Plastic Rod")
        f_rod_info = config.RODS.get(f_rod) if hasattr(config, 'RODS') else None 
        # Note: config might not have RODS if it's in cau_ca consts. Ideally we import from cau_ca or utils. 
        # But importing cogs is circular. Let's just stringify or peek DB.
        # We can use emoji maps if available in utils.
        
        # --- BUILD EMBED ---
        embed = discord.Embed(
            title=f"👤 HỒ SƠ NGƯỜI CHƠI: {target_user.display_name.upper()}",
            description=f"Thành viên của **{interaction.guild.name}**",
            color=config.COLOR_INFO
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # --- SECTION: ECONOMY ---
        eco_text = (
            f"💰 **Tài Sản:** {total_points:,.2f} Coiz {emojis.ANIMATED_EMOJI_COIZ}\n"
            f"📅 **Daily Streak:** {daily_streak} ngày {emojis.STREAK}"
        )
        embed.add_field(name="🏦 KINH TẾ", value=eco_text, inline=False)
        
        # --- SECTION: WORD GAME ---
        word_text = (
            f"🎮 **Số Game:** {w_played}\n"
            f"🎯 **Chính Xác:** {w_accuracy:.1f}%\n"
            f"📝 **Từ Dài Nhất:** {w_longest}"
        )
        embed.add_field(name="🔤 GAME NỐI TỪ", value=word_text, inline=True)
        
        # --- SECTION: FISHING ---
        # Generate Progress Bar for XP
        pct = min(1.0, f_xp / max(1, f_next_xp))
        bar_len = 8
        filled = int(pct * bar_len)
        bar = "🟦" * filled + "⬜" * (bar_len - filled)
        
        fish_text = (
            f"⭐ **Level:** {f_level} (Rank #{fishing_rank})\n"
            f"🧩 **XP:** {bar} ({f_xp:,}/{f_next_xp:,})\n"
            f"🎣 **Cần Chính:** {f_rod}"
        )
        embed.add_field(name="🐟 GAME CÂU CÁ", value=fish_text, inline=True)
        
        # --- SECTION: BADGES / ACHIEVEMENTS (Optional) ---
        # Collect badges from fishing stats
        badges = fishing_stats.get("badges", [])
        if badges:
            # Simple icon list to save space
            # We assume we can't easily map back to Badge Objects without import, 
            # but we know badge keys.
            badge_str = ""
            count = 0
            for b_key in badges:
                # Try simple mapping or just count
                badge_str += "🏅 " 
                count += 1
                if count >= 5: 
                    badge_str += "..."
                    break
            
            embed.add_field(name=f"🏆 THÀNH TỰU ({len(badges)})", value=f"Đã đạt {len(badges)} huy hiệu câu cá!", inline=False)

        embed.set_footer(text=f"ID: {target_user.id} | Gõ /help để xem danh sách lệnh")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="daily", description="📅 Điểm danh hằng ngày nhận Coiz")
    async def daily(self, interaction: discord.Interaction):
        """Nhận coiz hằng ngày. Reset lúc 7h sáng VN."""
        from datetime import datetime, timedelta, time
        import zoneinfo
        
        # Timezone setup
        vn_tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
        now = datetime.now(vn_tz)
        
        # Calculate 'Today's 7AM' and 'Yesterday's 7AM' relative to now
        # If now is before 7AM, 'Today 7AM' is actually yesterday relative to calendar, 
        # but let's define the "Daily Cycle" strictly.
        # Cycle N: From Day N 7:00 AM to Day N+1 6:59:59 AM.
        
        today_7am = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now < today_7am:
            today_7am = today_7am - timedelta(days=1)
            
        next_reset = today_7am + timedelta(days=1)
        prev_reset = today_7am - timedelta(days=1) # The start of the PREVIOUS cycle
        
        # Get user data
        last_daily_claim, daily_streak, last_daily_reward = await self.db.get_daily_info(interaction.user.id)
        
        # Parsing last_daily_claim from DB (it's string or timestamp)
        # SQLite stores TIMESTAMP as string 'YYYY-MM-DD HH:MM:SS' usually in UTC
        # We need to be careful with Timezones. 
        # CURRENT_TIMESTAMP in SQLite is UTC.
        # So we should convert checks to UTC or convert DB time to VN.
        # Easiest: Convert EVERYTHING to UTC for comparison? Or everything to VN.
        # Let's use UTC for logic consistency if DB uses UTC.
        
        # Re-calc times in UTC
        now_utc = datetime.now(zoneinfo.ZoneInfo("UTC"))
        
        # VN 7AM is UTC 0:00 (midnight)
        # Wait, VN is +7. So 7AM VN = 00:00 UTC.
        # So the daily reset is actually at 00:00 UTC. That makes it very simple.
        
        today_reset_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        # If we are strictly using VN 7AM == UTC 0:00 (which is true),
        # Then `last_daily_claim` (UTC) just needs to be compared to `today_reset_utc`.
        
        claimed = False
        streak_valid = False
        
        if last_daily_claim:
             # Parse DB timestamp. Format: "2023-10-27 10:00:00" or similar
            try:
                # If it has decimal seconds or not
                last_claim_dt = datetime.fromisoformat(last_daily_claim)
                # Assume DB stores naive UTC
                last_claim_dt = last_claim_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
            except ValueError:
                # Fallback layout
                try:
                    last_claim_dt = datetime.strptime(last_daily_claim, "%Y-%m-%d %H:%M:%S")
                    last_claim_dt = last_claim_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                except:
                     # Fail safe
                    last_claim_dt = None

            if last_claim_dt:
                if last_claim_dt >= today_reset_utc:
                     claimed = True
                elif last_claim_dt >= (today_reset_utc - timedelta(days=1)):
                     streak_valid = True
        
        if claimed:
            # Calculate time left
            time_left = next_reset - now # This uses mismatched TZs if next_reset is VN
            # Let's stick to UTC for calc
            next_reset_utc = today_reset_utc + timedelta(days=1)
            time_left = next_reset_utc - now_utc
            
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            await interaction.response.send_message(
                f"🛑 Bạn đã điểm danh hôm nay rồi! Quay lại sau **{hours}h {minutes}m** nữa nhé.",
                ephemeral=True
            )
            return

        # Calculate Reward
        base_reward = 10000
        new_streak = daily_streak + 1 if streak_valid else 1
        
        if new_streak == 1:
            reward = base_reward
        else:
            # "ngày thứ 3 sẽ được thêm 5% của ngày thứ 2"
            # Logic: If streak > 1, Reward = Last_Reward * 1.05
            # If last_daily_reward is 0 or missing (e.g. first time since update), assume logic Base * 1.05^(n-1)?
            # User said: "ngày đầu... 10000... ngày sau them 5% của ngay dau tien..."
            # Let's rely on 'last_daily_reward' from DB if streak continues.
            if last_daily_reward > 0:
                reward = last_daily_reward * 1.05
            else:
                 # Fallback if streak exists but no recorded reward (migration case)
                reward = base_reward * (1.05 ** (new_streak - 1))
        
        # Cap reward? User didn't specify. Exponential growth is dangerous.
        # 10000 * 1.05^365 is huge. 1.05^30 = 4.3x. 1.05^365 ~ 54,000,000.
        # I'll enable it as requested but maybe warn? No, just do as asked.
        
        # Update DB
        await self.db.update_daily(interaction.user.id, reward, new_streak)
        
        # Response
        embed = discord.Embed(
            title="📅 Điểm danh hàng ngày",
            description=f"Bạn đã nhận được **{reward:,.2f}** Coiz {emojis.ANIMATED_EMOJI_COIZ}",
            color=config.COLOR_SUCCESS
        )
        if new_streak > 1:
            embed.add_field(name="🔥 Chuỗi đăng nhập", value=f"{new_streak} ngày", inline=True)
            embed.add_field(name="📈 Tăng trưởng", value="+5%", inline=True)
        else:
            embed.add_field(name="🔥 Chuỗi đăng nhập", value="1 ngày (Bắt đầu chuỗi mới)", inline=True)
            
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Reset mỗi ngày lúc 7:00 sáng. Đừng bỏ lỡ!")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function cho cog"""
    await bot.add_cog(LeaderboardCog(bot, bot.db))
