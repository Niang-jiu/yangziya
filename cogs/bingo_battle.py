import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# --- 遊戲核心引擎 ---
class BingoEngine:
    def __init__(self, p1: discord.Member, p2: discord.Member, bet: int):
        self.p1 = p1
        self.p2 = p2
        self.bet = bet
        
        # 隨機分配貓狗
        if random.choice([True, False]):
            self.cat_player = p1
            self.dog_player = p2
        else:
            self.cat_player = p2
            self.dog_player = p1
            
        # 隨機生成 3x3 盤面，0 代表貓(🐱)，1 代表狗(🐶)
        self.grid = [[random.choice([0, 1]) for _ in range(3)] for _ in range(3)]
        
        # 玩家選擇 (None 代表未選, 0 代表不反轉, 1~9 代表對應格子)
        self.cat_choice = None
        self.dog_choice = None

    def render_grid(self):
        """將二維陣列轉換為表情符號顯示"""
        emojis = {0: "🐱", 1: "🐶"}
        result = ""
        for row in self.grid:
            result += "".join([emojis[cell] for cell in row]) + "\n"
        return result
        
    def resolve_game(self):
        """結算雙方的選擇與翻轉"""
        # 超時防呆：若沒選則視為 0 (不反轉)
        if self.cat_choice is None: self.cat_choice = 0
        if self.dog_choice is None: self.dog_choice = 0
        
        log = []
        
        # 判斷翻轉
        if self.cat_choice == self.dog_choice and self.cat_choice != 0:
            log.append("雙方選擇ㄌ同一個格子")
        else:
            if self.cat_choice != 0:
                # 貓方翻轉 (1~9 轉為陣列的 y, x)
                idx = self.cat_choice - 1
                y, x = idx // 3, idx % 3
                self.grid[y][x] = 1 - self.grid[y][x] # 0變1, 1變0
                log.append(f"貓方翻轉ㄌ第 {self.cat_choice} 格")
            else:
                log.append("貓方選擇ㄌ不反轉")
                
            if self.dog_choice != 0:
                idx = self.dog_choice - 1
                y, x = idx // 3, idx % 3
                self.grid[y][x] = 1 - self.grid[y][x]
                log.append(f"狗方翻轉ㄌ第 {self.dog_choice} 格")
            else:
                log.append("狗方選擇ㄌ不反轉")
                
        return log
        
    def calculate_lines(self):
        """計算連線數"""
        cat_lines = 0
        dog_lines = 0
        
        # 所有可能的連線組合 (座標)
        lines = [
            [(0,0), (0,1), (0,2)], [(1,0), (1,1), (1,2)], [(2,0), (2,1), (2,2)], # 橫線
            [(0,0), (1,0), (2,0)], [(0,1), (1,1), (2,1)], [(0,2), (1,2), (2,2)], # 直線
            [(0,0), (1,1), (2,2)], [(0,2), (1,1), (2,0)]                         # 對角線
        ]
        
        for line in lines:
            # 檢查這條線上的所有格子是否都是 0 (貓) 或是 1 (狗)
            values = [self.grid[y][x] for y, x in line]
            if all(v == 0 for v in values):
                cat_lines += 1
            elif all(v == 1 for v in values):
                dog_lines += 1
                
        return cat_lines, dog_lines


# --- 隱藏操作面板 ---
class BingoControlView(discord.ui.View):
    def __init__(self, main_view, player: discord.Member, is_cat: bool):
        super().__init__(timeout=None)
        self.main_view = main_view
        self.player = player
        self.is_cat = is_cat
        
        # 產生 1~9 的灰色按鈕
        for i in range(1, 10):
            row = (i - 1) // 3
            btn = discord.ui.Button(label=str(i), style=discord.ButtonStyle.secondary, row=row)
            btn.callback = self.make_callback(i)
            self.add_item(btn)
            
        # 放棄反轉按鈕
        pass_btn = discord.ui.Button(label="不反轉 (Pass)", style=discord.ButtonStyle.primary, row=3)
        pass_btn.callback = self.make_callback(0)
        self.add_item(pass_btn)

    def make_callback(self, choice: int):
        async def callback(interaction: discord.Interaction):
            if self.main_view.game_over:
                return await interaction.response.send_message("沒ㄌ", ephemeral=True)
            if interaction.user != self.player:
                return await interaction.response.send_message("不要亂點", ephemeral=True)
                
            # 檢查是否已選擇過
            if (self.is_cat and self.main_view.engine.cat_choice is not None) or \
               (not self.is_cat and self.main_view.engine.dog_choice is not None):
                return await interaction.response.send_message("你已經選ㄌ", ephemeral=True)

            # 記錄選擇
            if self.is_cat:
                self.main_view.engine.cat_choice = choice
            else:
                self.main_view.engine.dog_choice = choice
                
            choice_text = f"第 {choice} 格" if choice != 0 else "不反轉"
            await interaction.response.edit_message(content=f"已鎖定選擇：**{choice_text}**", view=None)
            
            # 檢查雙方是否都已完成選擇
            await self.main_view.check_both_submitted()

        return callback


# --- 遊戲主畫面 ---
class BingoMainView(discord.ui.View):
    def __init__(self, engine: BingoEngine, bot):
        super().__init__(timeout=None)
        self.engine = engine
        self.bot = bot
        self.message = None
        self.game_over = False
        self.timer_task = None
        
    def get_display_text(self, log=None):
        cat = self.engine.cat_player
        dog = self.engine.dog_player
        
        text = f"**對戰冰狗 - 賭注 {self.engine.bet} 元**\n"
        text += f"🐱 貓方：{cat.mention}\n"
        text += f"🐶 狗方：{dog.mention}\n\n"
        
        if not self.game_over:
            text += "**【當前盤面】**\n"
            text += self.engine.render_grid()
            text += "\n⏳ 雙方請在 **60秒** 內點擊下方按鈕選擇要反轉的格子！"
            
            cat_status = "準備" if self.engine.cat_choice is not None else "思考"
            dog_status = "準備" if self.engine.dog_choice is not None else "思考"
            text += f"\n\n🐱 : {cat_status}\n🐶 : {dog_status}"
        else:
            text += "**【最終結算】**\n"
            if log:
                text += "\n".join(log) + "\n\n"
            text += self.engine.render_grid() + "\n"
            
        return text

    @discord.ui.button(label="召喚 🐱 貓方操作面板", style=discord.ButtonStyle.secondary, emoji="🐱")
    async def btn_cat_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over: return await interaction.response.send_message("沒ㄌ", ephemeral=True)
        if interaction.user != self.engine.cat_player: return await interaction.response.send_message("不要亂點", ephemeral=True)
        if self.engine.cat_choice is not None: return await interaction.response.send_message("你選ㄌ", ephemeral=True)
        
        view = BingoControlView(self, interaction.user, is_cat=True)
        await interaction.response.send_message("只能選一格", view=view, ephemeral=True)

    @discord.ui.button(label="召喚 🐶 狗方操作面板", style=discord.ButtonStyle.secondary, emoji="🐶")
    async def btn_dog_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over: return await interaction.response.send_message("沒ㄌ", ephemeral=True)
        if interaction.user != self.engine.dog_player: return await interaction.response.send_message("不要亂點", ephemeral=True)
        if self.engine.dog_choice is not None: return await interaction.response.send_message("你選ㄌ", ephemeral=True)
        
        view = BingoControlView(self, interaction.user, is_cat=False)
        await interaction.response.send_message("只能選一格", view=view, ephemeral=True)

    async def start_timer(self):
        """60 秒倒數計時器"""
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return # 若提早雙方都選完，任務會被取消
            
        if not self.game_over:
            # 時間到，強制進行結算
            await self.check_both_submitted(is_timeout=True)

    async def check_both_submitted(self, is_timeout=False):
        # 若不是因為超時進來的，就檢查是否兩邊都選好了
        if not is_timeout:
            if self.engine.cat_choice is None or self.engine.dog_choice is None:
                # 只有一邊選好，更新主畫面的狀態文字
                await self.message.edit(content=self.get_display_text(), view=self)
                return

        # ==========================
        # 雙方皆完成或超時，進入結算
        # ==========================
        self.game_over = True
        if self.timer_task:
            self.timer_task.cancel()
            
        for child in self.children:
            child.disabled = True # 鎖死按鈕

        # 執行遊戲邏輯
        log = self.engine.resolve_game()
        cat_lines, dog_lines = self.engine.calculate_lines()
        
        log.append(f"🐱 貓方：{cat_lines} 條\n🐶 狗方：{dog_lines} 條")
        
        # 經濟結算
        economy = self.bot.get_cog("Economy")
        if cat_lines == dog_lines:
            log.append("**平手**")
        else:
            diff = abs(cat_lines - dog_lines)
            penalty = diff * self.engine.bet
            
            if cat_lines > dog_lines:
                winner, loser = self.engine.cat_player, self.engine.dog_player
            else:
                winner, loser = self.engine.dog_player, self.engine.cat_player
                
            log.append(f"**{winner.mention} 贏ㄌ**")
            log.append(f"**{loser.display_name} 輸ㄌ {penalty} 元**")
            
            if economy:
                # 更新金錢
                economy.update_balance(loser.id, -penalty)
                economy.update_balance(winner.id, penalty)
                log.append("")
            else:
                log.append("*(未載入經濟系統，無法扣款)*")

        await self.message.edit(content=self.get_display_text(log=log), view=self)


# --- 等待加入的大廳 ---
class BingoJoinView(discord.ui.View):
    def __init__(self, bet: int, max_risk: int, bot, host: discord.Member):
        super().__init__(timeout=120)
        self.bet = bet
        self.max_risk = max_risk
        self.bot = bot
        self.host = host
        self.message = None
        self.players = [] # 追蹤已加入的玩家

    @discord.ui.button(label="加入對局 (0/2)", style=discord.ButtonStyle.success)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 檢查是否重複加入
        if interaction.user in self.players:
            return await interaction.response.send_message("你加入ㄌ", ephemeral=True)
            
        # 資金防呆檢查
        economy = self.bot.get_cog("Economy")
        if economy:
            bal = economy.get_balance(interaction.user.id)
            if bal < self.max_risk:
                return await interaction.response.send_message(f"你太窮ㄌ", ephemeral=True)

        self.players.append(interaction.user)

        # 只有 1 人加入時，更新按鈕跟大廳文字
        if len(self.players) == 1:
            button.label = "加入對局 (1/2)"
            new_content = (
                f"**對戰冰果**\n"
                f"賭注：**{self.bet}** 元\n"
                f"**目前已準備 (1/2)**：{self.players[0].mention}"
            )
            await interaction.response.edit_message(content=new_content, view=self)
            
        # 2 人到齊，開局！
        elif len(self.players) == 2:
            self.stop() # 停止大廳倒數
            
            engine = BingoEngine(self.players[0], self.players[1], self.bet)
            game_view = BingoMainView(engine, self.bot)
            
            await interaction.response.edit_message(content="開始", view=None) 
            
            msg = await interaction.followup.send(content=game_view.get_display_text(), view=game_view)
            game_view.message = msg
            game_view.timer_task = asyncio.create_task(game_view.start_timer()) # 啟動 60 秒計時器

    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(content="不等ㄌ", view=None)
        except:
            pass


# --- Cog 指令註冊區 ---
class BingoGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="遊戲-對戰冰果", description="對戰型九宮格冰果")
    @app_commands.describe(賭注="單條線的基礎賭金 (0~10000)")
    async def start_bingo(self, interaction: discord.Interaction, 賭注: int):
        if 賭注 < 0 or 賭注 > 10000:
            return await interaction.response.send_message("賭注必須在 0 到 10000 之間！", ephemeral=True)
            
        # 最大潛在虧損：對方全滿(8條線) 自己0條線 -> 輸 8 條線
        max_risk = 賭注 * 8
                
        # 建立大廳 (發起人純開房，資金檢查移交給按鈕)
        view = BingoJoinView(bet=賭注, max_risk=max_risk, bot=self.bot, host=interaction.user)
        
        intro_text = (
            f"**對戰冰果**\n"
            f"賭注：**{賭注}** 元\n"
            f"**目前已準備 (0/2)**："
        )
        
        await interaction.response.send_message(content=intro_text, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(BingoGameCog(bot))