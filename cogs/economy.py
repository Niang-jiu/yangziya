import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs('data', exist_ok=True)
        self.data_file = 'data/economy.json'
        self.data = self.load_data()

        # 請將這裡的數字替換成你自己的 Discord User ID
        self.admin_id = 1141364674240204821 

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def get_balance(self, user_id: int) -> int:
        return self.data.get(str(user_id), 0)

    def update_balance(self, user_id: int, amount: int) -> bool:
        """
        更新餘額。
        如果是扣款 (amount 為負數)，會自動檢查餘額是否足夠。
        回傳 True 代表更新成功，回傳 False 代表餘額不足。
        """
        uid = str(user_id)
        current = self.get_balance(user_id)
        
        if current + amount < 0:
            return False
            
        self.data[uid] = current + amount
        self.save_data()
        return True

    # ==========================
    # Discord 指令區
    # ==========================
    @app_commands.command(name="經濟-查看餘額", description="查看目前的餘額")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        bal = self.get_balance(target.id)
        await interaction.response.send_message(f"{target.display_name} 的帳戶餘額為：{bal}")

    @app_commands.command(name="經濟-給錢", description="給其他玩家錢")
    async def pay(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        # 取得發送者 (自己) 的餘額
        bal = self.get_balance(interaction.user.id)
        
        if amount <= 0:
            return await interaction.response.send_message("要大於0ㄛ", ephemeral=True)
        if target.id == interaction.user.id:
            return await interaction.response.send_message("不要轉給自己", ephemeral=True)
        
        success = self.update_balance(interaction.user.id, -amount)
        if not success:
            # 加上 f 讓變數生效
            return await interaction.response.send_message(f"你只有{bal}", ephemeral=True)

        self.update_balance(target.id, amount)
        
        await interaction.response.send_message(f"成功轉帳 {amount} 給 {target.mention}。")

    @app_commands.command(name="陽子鴨-經濟-調整", description="調整玩家的金錢")
    async def addmoney(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        # 權限檢查：只有你的 ID 可以執行
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message("不認識你", ephemeral=True)

        if amount <= 0:
            return await interaction.response.send_message("發放金額必須大於 0。", ephemeral=True)

        self.update_balance(target.id, amount)
        
        await interaction.response.send_message(f"已成功發放 {amount} 給 {target.mention}。")

async def setup(bot):
    await bot.add_cog(Economy(bot))