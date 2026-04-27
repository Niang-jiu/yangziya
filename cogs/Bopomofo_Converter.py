import discord
from discord.ext import commands
import requests

class ZhuyinTranslator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # 忽略機器人本身
        if message.author.bot:
            return

        # 觸發條件
        if message.content.startswith(".abc "):
            # 1. 擷取內容
            content = message.content[5:]
            if not content:
                return

            # 2. 【核心修復 1】強制轉小寫，解決大寫鎖定導致 API 罷工的問題
            content = content.lower()

            # 3. 【核心修復 2】先清掉頭尾不小心多打的空白
            content = content.strip()
            if not content:
                return

            # 4. 【核心修復 3】精準判斷聲調
            # 6=ˊ, 3=ˇ, 4=ˋ, 7=˙, 空白=一聲
            # 只有在字串結尾不是這些合法聲調時，才補上 API 需要的 1 聲 (空格)
            if content[-1] not in "6347 ":
                content += " "

            url = "https://inputtools.google.com/request"
            params = {
                "text": content,
                "itc": "zh-hant-t-i0-und",
                "num": 1,
                "cp": 0,
                "cs": 1,
                "ie": "utf-8",
                "oe": "utf-8",
                "app": "discordbot"
            }
            
            try:
                # 加上 timeout 防止 API 卡住
                response = requests.get(url, params=params, timeout=5)
                data = response.json()
                
                # 5. 【核心修復 4】嚴格的安全檢查
                # 確保回傳是 SUCCESS，且 Google 真的有吐出翻譯結果
                if data[0] == 'SUCCESS' and len(data[1]) > 0:
                    results = data[1][0][1]
                    if results:  # 如果有成功組合成文字
                        translated = results[0]
                        await message.reply(f"✨ {translated}")
                    else:
                        # 處理「標點符號亂入」或「不存在的注音組合」
                        await message.reply("❌ 翻譯失敗：這串亂碼包含無效的注音組合或標點符號。")
            except Exception as e:
                pass

async def setup(bot):
    await bot.add_cog(ZhuyinTranslator(bot))