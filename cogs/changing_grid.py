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
            return await interaction.response.send_message("不要亂點！", ephemeral=True)

        # 判斷是否點擊正確
        if self.x == self.view_game.target_x and self.y == self.view_game.target_y:
            self.style = discord.ButtonStyle.success
            self.label = "✅"
            result_text = "**答對ㄌ！**"
        else:
            self.style = discord.ButtonStyle.danger
            self.label = "❌"
            result_text = "**答錯ㄌ！愚蠢！**"
            # 貼心地幫玩家標出正確答案在哪裡
            for child in self.view_game.children:
                if isinstance(child, GridButton) and child.x == self.view_game.target_x and child.y == self.view_game.target_y:
                    child.style = discord.ButtonStyle.success
                    child.label = "🎯"
        
        # 停用所有按鈕
        for child in self.view_game.children:
            child.disabled = True
            
        await interaction.response.edit_message(content=result_text, view=self.view_game)
        self.view_game.stop()

class GameView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player
        
        # 隨機產生起點座標
        self.start_x = random.randint(0, 4)
        self.start_y = random.randint(0, 4)
        
        # 隨機產生初始面向 (0:上, 1:右, 2:下, 3:左)
        self.start_o = random.randint(0, 3) 
        self.o_emojis = {0: '🔼', 1: '▶️', 2: '🔽', 3: '◀️'}

        # 移動邏輯輔助函數（處理穿牆/邊界循環）
        def move(x, y, o, steps):
            if o == 0: y -= steps   # 朝上
            elif o == 1: x += steps # 朝右
            elif o == 2: y += steps # 朝下
            elif o == 3: x -= steps # 朝左
            return x % 5, y % 5, o

        # 決定要走幾步 (3 到 5 步)
        num_steps = random.randint(3, 5)
        curr_x, curr_y, curr_o = self.start_x, self.start_y, self.start_o
        
        self.rule_texts = []
        
        # 動態產生超進化版複合動作
        for i in range(num_steps):
            steps = random.randint(1, 100) # 1~100步隨機大洗牌
            action_type = random.randint(1, 6)
            
            if action_type == 1:
                # 類型 1: 單純大步數移動
                dir_type = random.choice(["前進", "後退"])
                st = steps if dir_type == "前進" else -steps
                text = f"👣 {dir_type} {steps} 格"
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, st)
                
            elif action_type == 2:
                # 類型 2: 轉向後移動
                turn_type = random.choice(["左轉", "右轉", "迴轉"])
                turn_val = -1 if turn_type == "左轉" else (1 if turn_type == "右轉" else 2)
                dir_type = random.choice(["前進", "後退"])
                st = steps if dir_type == "前進" else -steps
                text = f"{turn_type}後{dir_type} {steps} 格"
                curr_o = (curr_o + turn_val) % 4
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, st)
                
            elif action_type == 3:
                # 類型 3: 夾心餅乾 (轉向 -> 移動 -> 轉向)
                turn1 = random.choice(["左轉", "右轉"])
                t1_val = -1 if turn1 == "左轉" else 1
                turn2 = random.choice(["左轉", "右轉"])
                t2_val = -1 if turn2 == "左轉" else 1
                text = f"{turn1}前進 {steps} 格後，立刻{turn2}"
                curr_o = (curr_o + t1_val) % 4
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, steps)
                curr_o = (curr_o + t2_val) % 4
                
            elif action_type == 4:
                # 類型 4: 連續轉向後移動
                turn1 = random.choice(["左轉", "右轉"])
                text = f"{turn1}後再{turn1}，接著前進 {steps} 格"
                t1_val = -1 if turn1 == "左轉" else 1
                curr_o = (curr_o + t1_val * 2) % 4
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, steps)
                
            elif action_type == 5:
                # 類型 5: 軸向鏡像 + 移動
                mirror_type = random.choice(["左右", "上下"])
                if mirror_type == "左右":
                    text = f"畫面左右翻轉後，前進 {steps} 格"
                    curr_x = (4 - curr_x) % 5
                    if curr_o == 1: curr_o = 3  # 面向右變左
                    elif curr_o == 3: curr_o = 1
                    st = steps
                else:
                    text = f"畫面上下翻轉後，後退 {steps} 格"
                    curr_y = (4 - curr_y) % 5
                    if curr_o == 0: curr_o = 2  # 面向上變下
                    elif curr_o == 2: curr_o = 0
                    st = -steps
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, st)
                
            else: 
                # 類型 6: 中心對稱 + 移動
                text = f"中心點對稱翻轉後，前進 {steps} 格"
                curr_x = (4 - curr_x) % 5
                curr_y = (4 - curr_y) % 5
                curr_o = (curr_o + 2) % 4 # 中心對稱，面向也強制迴轉
                curr_x, curr_y, curr_o = move(curr_x, curr_y, curr_o, steps)

            self.rule_texts.append(f"`{i+1}.` {text}")
            
        self.target_x, self.target_y = curr_x, curr_y
        self.rule_display = "\n".join(self.rule_texts)

        # 建立 5x5 面板
        for y in range(5):
            for x in range(5):
                btn = GridButton(x, y, self)
                # 標示起點與初始方向
                if x == self.start_x and y == self.start_y:
                    btn.style = discord.ButtonStyle.primary
                    btn.label = self.o_emojis[self.start_o]
                self.add_item(btn)

    # 60 秒超時處理
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="⏳ **想太久ㄌ！愚蠢**", view=self)
        except:
            pass

# --- Cog 註冊 ---

class SpaceLogicGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gridgame", description="推演小遊戲！")
    async def play_game(self, interaction: discord.Interaction):
        view = GameView(player=interaction.user)
        
        msg_content = (
            f"**推演小遊戲** ({interaction.user.mention})\n"
            f"藍色方塊是起點，**箭頭代表你一開始的面向！**\n"
            f"環狀地圖（超出邊界會從另一邊繞出來），點出最終的格子！\n\n"
            f"📜 **步驟指示：**\n{view.rule_display}"
        )
        
        await interaction.response.send_message(msg_content, view=view)
        view.message = await interaction.original_response()

# 固定寫法
async def setup(bot):
    await bot.add_cog(SpaceLogicGame(bot))