import discord
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 這裡建立一個 !shutdown 的指令
    @commands.command(name="goodnight", description="晚安")
    async def shutdown(self, ctx):
        # --- 請將下方的數字替換成你的 Discord 帳號 ID ---
        owner_id = 1141364674240204821 

        # 檢查觸發指令的人是不是你本人
        if ctx.author.id != owner_id:
            await ctx.send("不認識你！")
            return

        # 如果是你本人，就發送道別訊息並關機
        await ctx.send("💤晚安")
        print("機器人已透過指令手動關閉。")
        await self.bot.close() # 安全斷開連線並關閉程式

# 這是讓主程式自動讀取這個檔案的固定寫法
async def setup(bot):
    await bot.add_cog(Admin(bot))