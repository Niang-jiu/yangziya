import discord
from discord.ext import commands, tasks
import datetime

# 1️⃣ 設定時區為台灣時間 (UTC+8)
# 這很重要，因為如果你以後把機器人放到雲端主機，主機時間通常是 UTC
tz = datetime.timezone(datetime.timedelta(hours=8))

# 2️⃣ 設定每天觸發的時間：23:50 (晚上 11:50)
send_time = datetime.time(hour=23, minute=50, tzinfo=tz)

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 3️⃣ 這裡請換成你要發送訊息的「頻道 ID」 (不是伺服器 ID 喔)
        self.target_channel_id = 1439874210724970588 
        
        # 啟動排程任務
        self.daily_message.start()

    # 當這個 Cog 被卸載時，自動取消任務，避免重複執行
    def cog_unload(self):
        self.daily_message.cancel()

    # 使用 tasks.loop 讓它在指定時間執行
    @tasks.loop(time=send_time)
    async def daily_message(self):
        # 抓取指定頻道
        channel = self.bot.get_channel(self.target_channel_id)
        
        if channel:
            # 4️⃣ 在這裡自訂你要發送的訊息內容
            await channel.send("簽簽簽~~~簽到了嗎?")
        else:
            print(f"找不到 ID 為 {self.target_channel_id} 的頻道，請檢查 ID 是否正確。")

    # 在排程任務正式開始前，先等待機器人完全登入並準備好
    @daily_message.before_loop
    async def before_daily_message(self):
        await self.bot.wait_until_ready()

# Setup 函式，讓主程式能載入這個 Cog
async def setup(bot):
    await bot.add_cog(Schedule(bot))