import discord
from discord.ext import commands
from discord import app_commands
import re
import json
import os
import emoji  # 🟢 記得引入這個新安裝的套件

# 1️⃣ 在這裡填入你允許使用此功能的「伺服器 ID」
ALLOWED_GUILDS = [
    1439874209999491074, 
    #1439874209999491074
]

class EmojiTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # 1. 讓機器人確保 data 資料夾存在，如果沒有就自動建立一個
        os.makedirs('data', exist_ok=True)
        
        # 2. 將存檔路徑改到 data 資料夾底下
        self.data_file = 'data/emoji_counts.json'
        
        self.counts = self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {} 

    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.counts, f, ensure_ascii=False, indent=4)

    # ==========================
    # 監聽器：即時統計 (加入內建表符)
    # ==========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        
        # 🛡️ 安全檢查
        if message.guild.id not in ALLOWED_GUILDS:
            return
        
        # 🟢 抓取自訂表符
        custom_emojis = re.findall(r'<a?:\w+:\d+>', message.content)
        # 🟢 抓取內建表符 (利用 emoji 套件)
        builtin_emojis = [e['emoji'] for e in emoji.emoji_list(message.content)]
        
        # 將兩種表符合併
        all_emojis = custom_emojis + builtin_emojis
        
        if all_emojis:
            guild_id = str(message.guild.id)
            if guild_id not in self.counts:
                self.counts[guild_id] = {}
            for e in all_emojis:
                self.counts[guild_id][e] = self.counts[guild_id].get(e, 0) + 1
            self.save_data()

    # ==========================
    # 指令 1：回溯歷史 (加入內建表符)
    # ==========================
    @app_commands.command(name="sync_emoji_history", description="回溯統計過去的表符使用量 (會花一點時間)")
    @app_commands.describe(limit="要往回抓每個頻道多少則訊息 (填 1000 就是每個頻道抓 1000 則)")
    async def sync_history(self, interaction: discord.Interaction, limit: int = 10000):
        if interaction.guild_id not in ALLOWED_GUILDS:
            await interaction.response.send_message("此伺服器未開放此功能！", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        
        guild_id = str(interaction.guild_id)
        if guild_id not in self.counts:
            self.counts[guild_id] = {}

        scanned_count = 0
        found_emojis = 0

        for channel in interaction.guild.text_channels:
            try:
                async for message in channel.history(limit=limit):
                    if message.author.bot: 
                        continue
                    
                    # 🟢 同樣抓取兩種表符
                    custom_emojis = re.findall(r'<a?:\w+:\d+>', message.content)
                    builtin_emojis = [e['emoji'] for e in emoji.emoji_list(message.content)]
                    all_emojis = custom_emojis + builtin_emojis

                    if all_emojis:
                        found_emojis += len(all_emojis)
                        for e in all_emojis:
                            self.counts[guild_id][e] = self.counts[guild_id].get(e, 0) + 1
                    
                    scanned_count += 1
            except discord.Forbidden:
                continue 

        self.save_data()
        await interaction.followup.send(f"✅ **歷史同步完成！**\n共掃描了 `{scanned_count}` 則歷史訊息，共找到 `{found_emojis}` 個表符。")

    # ==========================
    # 指令 2：查看排行榜 (加入三個選項)
    # ==========================
    @app_commands.command(name="emoji_rank", description="本伺服器的表符使用排行榜")
    @app_commands.describe(mode="排行榜種類")
    @app_commands.choices(mode=[
        app_commands.Choice(name="自訂表符", value="custom"),
        app_commands.Choice(name="內建表符", value="builtin"),
        app_commands.Choice(name="綜合排行榜", value="all"),
    ])
    async def emoji_rank(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        if interaction.guild_id not in ALLOWED_GUILDS:
            await interaction.response.send_message("此伺服器未開放此功能！", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        if guild_id not in self.counts or not self.counts[guild_id]:
            await interaction.response.send_message("目前還沒有任何表符的使用紀錄喔！", ephemeral=True)
            return

        # 取得目前伺服器「還存在」的自訂表符 ID
        current_emoji_ids = [str(e.id) for e in interaction.guild.emojis]
        valid_emojis = {}

        # 🟢 分類與過濾邏輯
        for emoji_str, count in self.counts[guild_id].items():
            # 判斷是否為自訂表符 (特徵是 < 開頭, > 結尾)
            is_custom = emoji_str.startswith('<') and emoji_str.endswith('>')

            if is_custom:
                # 只有在選擇「自訂」或「綜合」時才處理，且需經過存活驗證
                if mode.value in ["custom", "all"]:
                    match = re.search(r':(\d+)>', emoji_str)
                    if match and match.group(1) in current_emoji_ids:
                        valid_emojis[emoji_str] = count
            else:
                # 是內建表符，只有在選擇「內建」或「綜合」時才處理
                if mode.value in ["builtin", "all"]:
                    valid_emojis[emoji_str] = count

        if not valid_emojis:
            await interaction.response.send_message("在這個分類下沒有找到任何表符紀錄喔！", ephemeral=True)
            return

        # 依照次數由大到小排序
        sorted_emojis = sorted(valid_emojis.items(), key=lambda item: item[1], reverse=True)
        
        description = ""
        for rank, (emoji_item, count) in enumerate(sorted_emojis[:10], start=1):
            description += f"**第 {rank} 名** {emoji_item} ── 使用了 `{count}` 次\n\n"

        # 依照選擇的模式更改標題
        title_prefix = "自訂表符" if mode.value == "custom" else "內建表符" if mode.value == "builtin" else "🏆 綜合"

        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} {title_prefix}表符排行榜", 
            description=description, 
            color=discord.Color.gold()
        )
        embed.set_footer(text="用這麼多幹嘛")
        
        await interaction.response.send_message(embed=embed)

# 設定 Cog 載入
async def setup(bot):
    await bot.add_cog(EmojiTracker(bot))