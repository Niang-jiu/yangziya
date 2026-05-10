import discord
from discord.ext import commands
from discord import app_commands
import random

# --- 遊戲 UI 元件 ---

class GridButton(discord.ui.Button):
    def __init__(self, x, y, view_game):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.view_game = view_game

    async def callback(self, interaction: discord.Interaction):
        # 防呆：檢查是不是呼叫指令的人點的
        if interaction.user != self.view_game.player:
            return await interaction.response.send_message("這不是你的遊戲面板喔！", ephemeral=True)

        if self.x == self.view_game.target_x and self.y == self.view_game.target_y:
            self.style = discord.ButtonStyle.success
            self.label = "✅"
            result_text = "🎉 **答對了！** 空間邏輯超強！"
        else:
            self.style = discord.ButtonStyle.danger
            self.label = "❌"
            result_text = f"💥 **答錯了！** 正確答案在從左數來第 {self.view_game.target_x + 1} 格，從上數來第 {self.view_game.target_y + 1} 格。"
        
        # 停用所有按鈕
        for child in self.view_game.children:
            child.disabled = True
            
        await interaction.response.edit_message(content=result_text, view=self.view_game)
        self.view_game.stop()

class GameView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player
        
        self.start_x = random.randint(0, 4)
        self.start_y = random.randint(0, 4)

        # 函數變換規則
        rules = [
            ("➡️ 向右兩格", lambda x, y: ((x + 2) % 5, y)),
            ("⬅️ 向左一格", lambda x, y: ((x - 1) % 5, y)),
            ("⬇️ 向下兩格", lambda x, y: (x, (y + 2) % 5)),
            ("⬆️ 向上兩格", lambda x, y: (x, (y - 2) % 5)),
            ("🪞 水平翻轉 (左右鏡像)", lambda x, y: (4 - x, y)),
            ("🪞 垂直翻轉 (上下鏡像)", lambda x, y: (x, 4 - y)),
            ("↘️ 向右一格，向下兩格", lambda x, y: ((x + 1) % 5, (y + 2) % 5))
        ]

        self.rule_text, rule_func = random.choice(rules)
        self.target_x, self.target_y = rule_func(self.start_x, self.start_y)

        # 建立 5x5 面板
        for y in range(5):
            for x in range(5):
                btn = GridButton(x, y, self)
                if x == self.start_x and y == self.start_y:
                    btn.style = discord.ButtonStyle.primary
                    btn.label = "🟦"
                self.add_item(btn)

    # 如果玩家 60 秒都沒點擊，就把按鈕停用
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="⏳ **超時啦！** 遊戲自動結束。", view=self)
        except:
            pass

# --- Cog 註冊 ---

class SpaceLogicGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gridgame", description="玩一局 5x5 空間邏輯小遊戲！")
    async def play_game(self, interaction: discord.Interaction):
        # 將觸發指令的玩家傳入 View，用來防止別人亂按
        view = GameView(player=interaction.user)
        
        await interaction.response.send_message(
            f"🎮 **空間邏輯挑戰** ({interaction.user.mention})\n藍色是你的起點！請依據提示點擊正確的目標格子。\n\n📜 **提示：** `{view.rule_text}`", 
            view=view
        )
        # 儲存 message 物件以便超時可以修改訊息
        view.message = await interaction.original_response()

# 固定寫法
async def setup(bot):
    await bot.add_cog(SpaceLogicGame(bot))