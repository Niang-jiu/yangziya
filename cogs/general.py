import discord
from discord.ext import commands
from discord import app_commands  # 1. 記得引入 app_commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 2. 裝飾器改成 @app_commands.command()
    # 建議加上 name 和 description，這會顯示在 Discord 的輸入介面上
    @app_commands.command(name="hello", description="叫機器人出來打招呼")
    async def hello(self, interaction: discord.Interaction): # 3. 參數 ctx 改成 interaction
        
        # 4. 回覆的方式改成 interaction.response.send_message()
        await interaction.response.send_message('幹嘛？我這不是來了嗎？')

# 這是讓主程式讀取這個檔案的固定寫法
async def setup(bot):
    await bot.add_cog(General(bot))