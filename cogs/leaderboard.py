"""
Leaderboard Cog - Bảng xếp hạng và thống kê
"""
import discord
from discord.ext import commands
from discord import app_commands

import config
from utils import embeds
from database.db_manager import DatabaseManager


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: DatabaseManager):
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
    
    @app_commands.command(name="stats", description="📊 Xem thống kê cá nhân")
    @app_commands.describe(user="Người chơi cần xem (để trống để xem của bạn)")
    async def stats(self, interaction: discord.Interaction, user: discord.User = None):
        """Hiển thị thống kê của người chơi"""
        target_user = user or interaction.user
        
        # Lấy stats từ database
        async with self.db.db_path as db_path:
            import aiosqlite
            async with aiosqlite.connect(db_path) as db:
                async with db.execute("""
                    SELECT total_points, games_played, words_submitted, 
                           correct_words, wrong_words, longest_word, longest_word_length
                    FROM player_stats
                    WHERE user_id = ? AND guild_id = ?
                """, (target_user.id, interaction.guild_id)) as cursor:
                    row = await cursor.fetchone()
        
        if not row:
            await interaction.response.send_message(
                f"🤷 {target_user.mention} chưa chơi game nào!",
                ephemeral=True
            )
            return
        
        # Tạo embed thống kê
        total_points, games_played, words_submitted, correct_words, wrong_words, longest_word, longest_word_length = row
        
        accuracy = (correct_words / words_submitted * 100) if words_submitted > 0 else 0
        
        embed = discord.Embed(
            title=f"📊 Thống kê của {target_user.display_name}",
            color=config.COLOR_INFO
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(
            name="🏆 Tổng Coinz",
            value=f"**{total_points:,}** coinz",
            inline=True
        )
        
        embed.add_field(
            name="🎮 Số Game Đã Chơi",
            value=f"**{games_played}** game",
            inline=True
        )
        
        embed.add_field(
            name="✍️ Tổng Từ Gửi",
            value=f"**{words_submitted}** từ",
            inline=True
        )
        
        embed.add_field(
            name="✅ Từ Đúng",
            value=f"**{correct_words}** từ",
            inline=True
        )
        
        embed.add_field(
            name="❌ Từ Sai",
            value=f"**{wrong_words}** từ",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Độ Chính Xác",
            value=f"**{accuracy:.1f}%**",
            inline=True
        )
        
        if longest_word:
            embed.add_field(
                name="🔥 Từ Dài Nhất",
                value=f"**{longest_word.upper()}** ({longest_word_length} ký tự)",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function cho cog"""
    db = DatabaseManager(config.DATABASE_PATH)
    await bot.add_cog(LeaderboardCog(bot, db))
