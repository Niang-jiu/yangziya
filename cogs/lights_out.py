import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# --- 遊戲進行中的按鈕 ---
class LightsOutButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="關", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: LightsOutView = self.view
        
        if interaction.user != view.player:
            return await interaction.response.send_message("不要幫別人點", ephemeral=True)

        view.toggle(self.x, self.y)
        
        if view.check_win():
            await view.end_game(interaction, win=True)
        else:
            view.update_board()
            await interaction.response.edit_message(view=view)

# --- 結算畫面的按鈕 ---
class PlayAgainButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="再玩")

    async def callback(self, interaction: discord.Interaction):
        view: LightsOutView = self.view
        if interaction.user != view.player:
            return await interaction.response.send_message("不要幫別人點", ephemeral=True)
        
        # 重置遊戲並切換回遊玩介面
        view.start_game()
        instruction = (
            "關燈"
        )
        await interaction.response.edit_message(content=instruction, embeds=[], view=view)

class EndButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="結束")

    async def callback(self, interaction: discord.Interaction):
        view: LightsOutView = self.view
        if interaction.user != view.player:
            return await interaction.response.send_message("不要幫別人點", ephemeral=True)
        
        # 取消結算畫面的計時器
        if view.end_task:
            view.end_task.cancel()

        # 直接拔掉整個 View (清除所有按鈕)，只留下原本的 Embed 訊息
        await interaction.response.edit_message(view=None)
        view.stop()

# --- 遊戲主控制面板 ---
class LightsOutView(discord.ui.View):
    def __init__(self, player, bot):
        super().__init__(timeout=None) # 取消內建的無動作超時，改用手動 Task 計算
        self.player = player
        self.bot = bot
        self.message = None
        self.grid = []
        self.buttons = []
        
        # 用來記錄遊戲狀態與計時任務
        self.state = 'init'
        self.game_task = None
        self.end_task = None
        
        self.start_game()

    def start_game(self):
        """初始化或重置盤面，並啟動 5 分鐘計時"""
        self.state = 'playing'
        
        # 如果有舊的計時任務，先取消掉
        if getattr(self, 'game_task', None):
            self.game_task.cancel()
        if getattr(self, 'end_task', None):
            self.end_task.cancel()

        self.grid = [[False for _ in range(5)] for _ in range(5)]
        
        for _ in range(random.randint(10, 20)):
            rx = random.randint(0, 4)
            ry = random.randint(0, 4)
            self._internal_toggle(rx, ry)
            
        self.build_playing_ui()
        
        # 啟動 5 分鐘 (300秒) 的強制結束計時器
        self.game_task = asyncio.create_task(self.game_timer(300))

    async def game_timer(self, duration):
        """遊戲 5 分鐘計時任務"""
        try:
            await asyncio.sleep(duration)
            if self.state == 'playing':
                await self.end_game(None, win=False, reason="timeout")
        except asyncio.CancelledError:
            pass # 任務被取消(例如通關了)不處理

    async def end_screen_timer(self, duration):
        """結算畫面 1 分鐘計時任務"""
        try:
            await asyncio.sleep(duration)
            if self.state == 'ended' and self.message:
                # 直接把 view 設為 None，把下方按鈕徹底刪除
                try:
                    await self.message.edit(view=None)
                except discord.HTTPException:
                    pass
                self.stop()
        except asyncio.CancelledError:
            pass

    def build_playing_ui(self):
        """建立 5x5 遊玩按鈕"""
        self.clear_items()
        self.buttons = []
        for y in range(5):
            row_btns = []
            for x in range(5):
                btn = LightsOutButton(x, y)
                self.add_item(btn)
                row_btns.append(btn)
            self.buttons.append(row_btns)
        self.update_board()

    def _internal_toggle(self, x, y):
        directions = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < 5 and 0 <= ny < 5:
                self.grid[ny][nx] = not self.grid[ny][nx]

    def toggle(self, x, y):
        self._internal_toggle(x, y)

    def update_board(self):
        for y in range(5):
            for x in range(5):
                btn = self.buttons[y][x]
                if self.grid[y][x]:
                    btn.style = discord.ButtonStyle.primary 
                    btn.label = "開"
                else:
                    btn.style = discord.ButtonStyle.secondary 
                    btn.label = "關"

    def check_win(self):
        for row in self.grid:
            if any(row): 
                return False
        return True

    def get_board_string(self):
        """將盤面轉換為純文字方塊供 Embed 顯示"""
        result = ""
        for row in self.grid:
            for cell in row:
                result += "□ " if cell else "■ "
            result += "\n"
        return f"```\n{result}```"

    async def end_game(self, interaction: discord.Interaction, win: bool, reason=""):
        """處理遊戲結束並切換至結算畫面"""
        self.state = 'ended'
        if self.game_task:
            self.game_task.cancel()
        
        # --- 第一個 Embed：遊戲資訊與盤面 ---
        embed1 = discord.Embed(color=0x2b2d31)
        embed1.set_author(name=f"{self.player.display_name} ({self.player.name})", icon_url=self.player.display_avatar.url)
        
        if win:
            status_text = "你贏了！"
        elif reason == "timeout":
            status_text = "想太久ㄌ"
        else:
            status_text = "失敗！"
            
        board_str = self.get_board_string()
        
        embed1.description = (
            "**點燈遊戲**\n\n"
            "過關獎勵：10\n\n"
            f"**{status_text}**\n\n"
            f"{board_str}"
        )
        embed1.set_footer(text="陽子鴨小遊戲", icon_url=self.bot.user.display_avatar.url)
        embed1.timestamp = discord.utils.utcnow()
        
        # --- 經濟系統處理 ---
        reward = 10 if win else 0
        bal = 0
        economy_cog = self.bot.get_cog("Economy")
        
        embed2 = discord.Embed(color=0x2b2d31)
        if economy_cog:
            if win:
                economy_cog.update_balance(self.player.id, reward)
            bal = economy_cog.get_balance(self.player.id)
            embed2.description = f"你贏了 {reward} 元\n餘額 {bal} 元\n"
        else:
            embed2.description = f"你贏了 {reward} 元\n(未載入經濟系統)\n"

        # --- 替換為結算按鈕 ---
        self.clear_items()
        self.add_item(PlayAgainButton())
        self.add_item(EndButton())
        
        if interaction:
            await interaction.response.edit_message(content=None, embeds=[embed1, embed2], view=self)
        elif self.message:
            await self.message.edit(content=None, embeds=[embed1, embed2], view=self)
            
        # 啟動 1 分鐘的結算畫面防呆計時器 (時間到就凍結按鈕)
        self.end_task = asyncio.create_task(self.end_screen_timer(60))

# --- Cog 註冊區 ---
class LightsOutGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="遊戲-點燈", description="點燈遊戲")
    async def play_lights_out(self, interaction: discord.Interaction):
        
        view = LightsOutView(interaction.user, self.bot)
        instruction = (
            "關燈"
        )
        
        await interaction.response.send_message(content=instruction, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(LightsOutGame(bot))