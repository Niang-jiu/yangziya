import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 1️⃣ 在這裡放入你所有的伺服器 ID (用逗號隔開)
GUILD_IDS = [
    1491481085018898514,  # 第一個伺服器 ID
    1439874209999491074   # 第二個伺服器 ID (請換成你真實的 ID)
]

class MyBot(commands.Bot):
    def __init__(self):
        # Intents 的 message_content 記得要開
        intents = discord.Intents.default()
        intents.message_content = True
        # 👇 這裡把觸發符號改成了 '.'
        super().__init__(command_prefix='.', intents=intents)

    # 把載入 Cogs 和註冊斜線指令都放在 setup_hook 裡
    async def setup_hook(self):
        # 1. 載入所有 Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'成功載入模組: {filename}')
        
        # 2️⃣ 利用迴圈，把指令同步到列表裡的所有伺服器
        for guild_id in GUILD_IDS:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            
        print(f"斜線指令同步完成，已同步至 {len(GUILD_IDS)} 個伺服器。")

bot = MyBot()

# (上半部程式碼保持不變...)

@bot.event
async def on_ready():
    print(f'{bot.user} 已經上線。')
    
    # 👇 新增：檢查是否有重啟留下的暫存檔
    if os.path.exists("restart_channel.txt"):
        # 讀取裡面的頻道 ID
        with open("restart_channel.txt", "r") as f:
            channel_id = int(f.read().strip())
        
        # 讀取完畢後，把暫存檔刪除（避免下次正常開機也亂叫）
        os.remove("restart_channel.txt")
        
        # 找到剛剛下指令的頻道，並發送重啟完畢的訊息
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send("醒ㄌ")

if __name__ == "__main__":
    # 既然繼承了 commands.Bot，直接 run 就可以了
    bot.run(TOKEN)