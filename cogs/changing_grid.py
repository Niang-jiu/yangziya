import discord
from discord.ext import commands
from discord import app_commands
import random
import time

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

        # 結算時間
        elapsed_time = round(time.time() - self.view_game.start_time, 2)

        # 判斷是否點擊正確
        if self.x == self.view_game.target_x and self.y == self.view_game.target_y:
            self.style = discord.ButtonStyle.success
            self.label = "✅"
            result_text = f"**答對ㄌ！**\n**{elapsed_time} 秒**"
        else:
            self.style = discord.ButtonStyle.danger
            self.label = "❌"
            result_text = f"**答錯ㄌ！愚蠢！**\n**想了 {elapsed_time} 秒還錯。**"
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
        self.start_time = time.time()  # 開始計時
        
        # 隨機產生起點座標
        self.start_x = random.randint(0, 4)
        self.start_y = random.randint(0, 4)
        
        # 隨機產生初始面向 (0:上, 1:右, 2:下, 3:左)
        self.start_o = random.randint(0, 3) 
        self.o_emojis = {0: '🔼', 1: '▶️', 2: '🔽', 3: '◀️'}

        # 移動邏輯輔助函數
        def move(x, y, o, steps):
            if o == 0: y -= steps   # 朝上
            elif o == 1: x += steps # 朝右
            elif o == 2: y += steps # 朝下
            elif o == 3: x -= steps # 朝左
            return x % 5, y % 5, o

        # 產生單一步驟的函數，回傳 (文字說明, 執行函數)
        def get_action():
            steps = random.randint(1, 100)
            action_type = random.randint(1, 6)
            
            if action_type == 1:
                dir_type = random.choice(["前進", "後退"])
                st = steps if dir_type == "前進" else -steps
                text = f"{dir_type} {steps} 格"
                def func(x, y, o, st=st): return move(x, y, o, st)
                return text, func
                
            elif action_type == 2:
                turn_type = random.choice(["左轉", "右轉", "迴轉"])
                turn_val = -1 if turn_type == "左轉" else (1 if turn_type == "右轉" else 2)
                dir_type = random.choice(["前進", "後退"])
                st = steps if dir_type == "前進" else -steps
                text = f"{turn_type}後{dir_type} {steps} 格"
                def func(x, y, o, tv=turn_val, st=st):
                    o = (o + tv) % 4
                    return move(x, y, o, st)
                return text, func
                
            elif action_type == 3:
                turn1 = random.choice(["左轉", "右轉"])
                t1_val = -1 if turn1 == "左轉" else 1
                turn2 = random.choice(["左轉", "右轉"])
                t2_val = -1 if turn2 == "左轉" else 1
                text = f"{turn1}前進 {steps} 格後，立刻{turn2}"
                def func(x, y, o, tv1=t1_val, tv2=t2_val, st=steps):
                    o = (o + tv1) % 4
                    x, y, o = move(x, y, o, st)
                    o = (o + tv2) % 4
                    return x, y, o
                return text, func
                
            elif action_type == 4:
                turn1 = random.choice(["左轉", "右轉"])
                text = f"{turn1}後再{turn1}，接著前進 {steps} 格"
                t1_val = -1 if turn1 == "左轉" else 1
                def func(x, y, o, tv=t1_val, st=steps):
                    o = (o + tv * 2) % 4
                    return move(x, y, o, st)
                return text, func
                
            elif action_type == 5:
                mirror_type = random.choice(["左右", "上下"])
                if mirror_type == "左右":
                    text = f"畫面左右翻轉後，前進 {steps} 格"
                    def func(x, y, o, st=steps):
                        x = (4 - x) % 5
                        if o == 1: o = 3
                        elif o == 3: o = 1
                        return move(x, y, o, st)
                    return text, func
                else:
                    text = f"畫面上下翻轉後，後退 {steps} 格"
                    def func(x, y, o, st=-steps):
                        y = (4 - y) % 5
                        if o == 0: o = 2
                        elif o == 2: o = 0
                        return move(x, y, o, st)
                    return text, func
                    
            else: 
                text = f"中心點對稱翻轉後，前進 {steps} 格"
                def func(x, y, o, st=steps):
                    x = (4 - x) % 5
                    y = (4 - y) % 5
                    o = (o + 2) % 4
                    return move(x, y, o, st)
                return text, func

        self.step_texts = []
        self.step_funcs = []
        
        # 生成前 5 個一般步驟
        for _ in range(5):
            text, func = get_action()
            self.step_texts.append(text)
            self.step_funcs.append(func)

        # 第 6 步：複合指令魔王關
        macro_type = random.choice(["repeat", "sequence"])
        if macro_type == "repeat":
            target_step = random.randint(1, 5)
            times = random.randint(2, 4)
            macro_text = f"將步驟 {target_step} 連續執行 {times} 次"
            def macro_func(x, y, o, t_step=target_step, t_times=times):
                for _ in range(t_times):
                    x, y, o = self.step_funcs[t_step-1](x, y, o)
                return x, y, o
        else:
            seq = random.sample(range(1, 6), 3) # 隨機抽 3 個前面不同的步驟
            macro_text = f"依序執行步驟 {seq[0]}, {seq[1]}, {seq[2]}"
            def macro_func(x, y, o, sequence=seq):
                for s in sequence:
                    x, y, o = self.step_funcs[s-1](x, y, o)
                return x, y, o

        self.step_texts.append(macro_text)
        self.step_funcs.append(macro_func)

        # 模擬一次完整計算，找出目標答案
        curr_x, curr_y, curr_o = self.start_x, self.start_y, self.start_o
        for func in self.step_funcs:
            curr_x, curr_y, curr_o = func(curr_x, curr_y, curr_o)
            
        self.target_x, self.target_y = curr_x, curr_y
        
        # 整理文字顯示
        rule_lines = [f"`{i+1}.` {text}" for i, text in enumerate(self.step_texts)]
        self.rule_display = "\n".join(rule_lines)

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
            await self.message.edit(content="⏳ **想太久ㄌ! 愚蠢", view=self)
        except:
            pass

# --- Cog 註冊 ---

class SpaceLogicGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gridgame", description="推演小遊戲")
    async def play_game(self, interaction: discord.Interaction):
        view = GameView(player=interaction.user)
        
        msg_content = (
            f"**推演小遊戲** ({interaction.user.mention})\n"
            f"藍色方塊是起點，**箭頭代表你一開始的面向！**\n"
            f"**步驟：**\n{view.rule_display}"
        )
        
        await interaction.response.send_message(msg_content, view=view)
        view.message = await interaction.original_response()

# 固定寫法
async def setup(bot):
    await bot.add_cog(SpaceLogicGame(bot))