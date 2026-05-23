import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import os
import certifi  # 👈 1. 新增引入這個憑證套件

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.mongo_uri = os.getenv('MONGODB_URI')
        
        # 👈 2. 這裡加上 tlsCAFile=certifi.where()，這是解決 Windows SSL 報錯的關鍵！
        self.client = MongoClient(self.mongo_uri, tlsCAFile=certifi.where())
        
        self.db = self.client['discord_bot']  # 資料庫名稱
        self.collection = self.db['economy']  # 集合名稱
        
        self.admin_id = 1141364674240204821 

    def get_balance(self, user_id: int) -> int:
        user_data = self.collection.find_one({"user_id": str(user_id)})
        return user_data.get("balance", 0) if user_data else 0

    def update_balance(self, user_id: int, amount: int) -> bool:
        uid = str(user_id)
        current = self.get_balance(user_id)
        
        if current + amount < 0:
            return False
            
        self.collection.update_one(
            {"user_id": uid},
            {"$set": {"balance": current + amount}},
            upsert=True
        )
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
        bal = self.get_balance(interaction.user.id)
        
        if amount <= 0:
            return await interaction.response.send_message("要大於0ㄛ", ephemeral=True)
        if target.id == interaction.user.id:
            return await interaction.response.send_message("不要轉給自己", ephemeral=True)
        
        success = self.update_balance(interaction.user.id, -amount)
        if not success:
            return await interaction.response.send_message(f"你只有{bal}", ephemeral=True)

        self.update_balance(target.id, amount)
        await interaction.response.send_message(f"成功轉帳 {amount} 給 {target.mention}。")

    @app_commands.command(name="陽子鴨-經濟-調整", description="調整玩家的金錢 (輸入正數加錢，負數扣錢)")
    async def addmoney(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        # 權限檢查：只有你的 ID 可以執行
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message("不認識你", ephemeral=True)

        # 擋掉 0 的情況，因為沒意義
        if amount == 0:
            return await interaction.response.send_message("調整金額不能為 0 喔！", ephemeral=True)

        # 執行更新
        success = self.update_balance(target.id, amount)
        
        # 如果是扣錢，而且玩家錢不夠扣 (因為你原先寫的 update_balance 如果扣完小於0會回傳 False)
        if not success:
            current_bal = self.get_balance(target.id)
            return await interaction.response.send_message(f"扣款失敗！{target.mention} 的餘額只有 {current_bal}，不夠扣。", ephemeral=True)

        # 根據是加錢還是扣錢，給予不同的成功訊息
        if amount > 0:
            await interaction.response.send_message(f"發ㄌ {amount} 給 {target.mention}。")
        else:
            # 使用 abs() 把負數轉成正數顯示，文字讀起來比較自然 (例如: 扣除 50，而不是扣除 -50)
            await interaction.response.send_message(f"從 {target.mention} 扣ㄌ {abs(amount)}。")

async def setup(bot):
    await bot.add_cog(Economy(bot))