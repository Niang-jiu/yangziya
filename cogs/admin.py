import discord
from discord.ext import commands
import os
import sys

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # --- 請將下方的數字替換成你的 Discord 帳號 ID ---
        self.owner_id = 1141364674240204821 

    # ==========================
    # 1. 關機指令 (.goodnight)
    # ==========================
    @commands.command(name="goodnight", description="晚安")
    async def shutdown(self, ctx):
        # 檢查觸發指令的人是不是你本人
        if ctx.author.id != self.owner_id:
            await ctx.send("不認識你！")
            return

        # 如果是你本人，就發送道別訊息並關機
        await ctx.send("💤 晚安")
        print("機器人已透過指令手動關閉。")
        await self.bot.close() # 安全斷開連線並關閉程式

    # ==========================
    # 2. 徹底重啟指令 (.morning)
    # ==========================
    @commands.command(name="morning", description="早安")
    async def restart(self, ctx):
        if ctx.author.id != self.owner_id:
            await ctx.send("不認識你！")
            return

        # 修改：重啟前的提示訊息可以改一下，讓你知道它正在動作
        await ctx.send("早安鴨鴨鴨")
        print("機器人已透過指令重啟。")
        
        # 👇 新增：把當前的頻道 ID 存進暫存檔
        with open("restart_channel.txt", "w") as f:
            f.write(str(ctx.channel.id))
        
        # 使用 os.execv 讓作業系統層級直接替換掉目前的進程
        os.execv(sys.executable, ['python'] + sys.argv)

    # ==========================
    # 3. 熱重載模組 (.reload)
    # ==========================
    @commands.command(name="reload", description="重新載入特定的 Cog 檔案")
    async def reload_cog(self, ctx, extension: str):
        # 防呆檢查：如果忘記打副檔名或多打了 .py 都能自動處理
        extension = extension.replace(".py", "")
        
        if ctx.author.id != self.owner_id:
            await ctx.send("不認識你！")
            return

        try:
            # 讓機器人重新讀取該檔案
            await self.bot.reload_extension(f"cogs.{extension}")
            await ctx.send(f"✅ 成功無縫更新模組：`{extension}.py`！")
        except Exception as e:
            await ctx.send(f"❌ 載入 `{extension}` 失敗，請檢查程式碼是否有 Bug:\n```py\n{e}\n```")

# 這是讓主程式自動讀取這個檔案的固定寫法
async def setup(bot):
    await bot.add_cog(Admin(bot))