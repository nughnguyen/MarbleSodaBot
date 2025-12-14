import discord
from discord import ui
import config
from utils import emojis
import urllib.parse
import datetime
import random
import time
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None


class DonationModal(ui.Modal):
    def __init__(self, method: str):
        super().__init__(title=f"Nạp qua {method}")
        self.method = method
        self.amount = ui.TextInput(
            label="Số tiền (VND)",
            placeholder="VD: 10000",
            min_length=4,
            max_length=10,
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount_val = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message("❌ Số tiền không hợp lệ. Vui lòng nhập số.", ephemeral=True)
            return

        if amount_val < config.MIN_DONATION_COINZ:
            await interaction.response.send_message(f"❌ Số tiền tối thiểu là {config.MIN_DONATION_COINZ} VND.", ephemeral=True)
            return

        # Generate Unique Order Code
        rand_code = random.randint(100000, 999999)
        order_content = f"GUMZ{rand_code}"
        
        # Calculate Rewards and Expiry
        coinz_reward = (amount_val // 1000) * config.COINZ_PER_1000VND
        expiry_seconds = 600 # 10 minutes
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=expiry_seconds)
        expiry_timestamp = int(expiry_time.timestamp())
        
        # Insert Pending Transaction to Supabase
        if config.SUPABASE_URL and config.SUPABASE_KEY and create_client:
            try:
                sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                sb.table('transactions').insert({
                    'user_id': interaction.user.id,
                    'amount': amount_val,
                    'description': order_content,
                    'status': 'pending',
                    'created_at': datetime.datetime.now().isoformat(),
                    'metadata': {'method': self.method}
                }).execute()
            except Exception as e:
                print(f"Error creating pending txn: {e}")
                # Fallback: Proceed without DB record (Bot will treat as new/legacy flow if webhook handles it)
        
        params = {
            'amount': amount_val,
            'content': order_content,
            'method': self.method,
            'userId': interaction.user.id,
            'userName': interaction.user.name,
            'expiry': expiry_timestamp
        }
        query_string = urllib.parse.urlencode(params)
        payment_url = f"{config.DONATION_WEB_URL}/payment?{query_string}"
        
        embed = discord.Embed(
            title="💳 Thanh Toán",
            description=(
                f"Bạn đã chọn nạp **{amount_val:,} VND** qua **{self.method}**.\n"
                f"Sẽ nhận được: **{coinz_reward:,} Coinz** {emojis.ANIMATED_EMOJI_COINZ}\n\n"
                f"**⚠️ LƯU Ý:**\n"
                f"1. Nội dung chuyển khoản: `{order_content}`\n"
                f"2. Giao dịch hết hạn sau: <t:{expiry_timestamp}:R>\n"
                f"3. Sau thời gian trên, nếu chuyển khoản sẽ **KHÔNG ĐƯỢC TÍNH**."
            ),
            color=config.COLOR_INFO,
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.set_footer(text="Vui lòng quét mã QR trên web để đảm bảo chính xác nhất.")
        
        # Create a view with a link button
        view = ui.View()
        view.add_item(ui.Button(label="THANH TOÁN NGAY", url=payment_url, style=discord.ButtonStyle.link, emoji="💸"))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class DonationView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="MOMO", style=discord.ButtonStyle.primary, emoji=emojis.EMOJI_MOMO_PAY if hasattr(emojis, 'EMOJI_MOMO_PAY') else "💸", row=0)
    async def momo_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DonationModal(method="MOMO"))

    @ui.button(label="VNPAY", style=discord.ButtonStyle.primary, emoji="💳", row=0)
    async def vnpay_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DonationModal(method="VNPAY"))

    @ui.button(label="VIETQR", style=discord.ButtonStyle.success, emoji="🏦", row=1)
    async def vietqr_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DonationModal(method="VIETQR"))


