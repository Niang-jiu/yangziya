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
        if interaction.user != self.view_game.player:
            return await interaction.response.send_message("不要亂點！", ephemeral=True)

        elapsed_time = round(time.time() - self.view_game.start_time, 2)

        # 🔒 絕對時間鎖
        if elapsed_time > 60:
            for child in self.view_game.children:
                child.disabled = True
                if isinstance(child, GridButton) and child.x == self.view_game.target_x and child.y == self.view_game.target_y:
                    child.style = discord.ButtonStyle.success
                    child.label = "🎯"
            
            await interaction.response.edit_message(content=f"⏳ **超過60秒ㄌ! 愚蠢**\n**(你花了 {elapsed_time} 秒)**", view=self.view_game)
            self.view_game.stop()
            await self.trigger_post_game(interaction)
            return

        # 判斷正確與否
        if self.x == self.view_game.target_x and self.y == self.view_game.target_y:
            self.style = discord.ButtonStyle.success
            self.label = "✅"
            result_text = f"**答對ㄌ！**\n**{elapsed_time} 秒**"
        else:
            self.style = discord.ButtonStyle.danger
            self.label = "❌"
            result_text = f"**答錯ㄌ！愚蠢！**\n**想了 {elapsed_time} 秒還錯。**"
            for child in self.view_game.children:
                if isinstance(child, GridButton) and child.x == self.view_game.target_x and child.y == self.view_game.target_y:
                    child.style = discord.ButtonStyle.success
                    child.label = "🎯"
        
        for child in self.view_game.children:
            child.disabled = True
            
        await interaction.response.edit_message(content=result_text, view=self.view_game)
        self.view_game.stop()
        await self.trigger_post_game(interaction)

    # 呼叫結算面板的輔助函數
    async def trigger_post_game(self, interaction):
        post_view = PostGameView(self.view_game.player, self.view_game.rule_display, self.view_game.message)
        post_msg = await interaction.followup.send(view=post_view, wait=True)
        post_view.message = post_msg


# =========================================
# 結算與控制面板 (負責回看與重開)
# =========================================
class PostGameView(discord.ui.View):
    def __init__(self, player: discord.Member, rule_display: str, game_message: discord.Message):
        super().__init__(timeout=300)
        self.player = player
        self.rule_display = rule_display
        self.game_message = game_message
        self.message = None

    @discord.ui.button(label="📜 回看題目", style=discord.ButtonStyle.secondary)
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"**【剛剛的題目】**\n{self.rule_display}", ephemeral=True)

    @discord.ui.button(label="🔄 重來一局", style=discord.ButtonStyle.primary)
    async def restart_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.player:
            return await interaction.response.send_message("你不是這局的玩家！想玩自己輸入指令", ephemeral=True)

        new_view = GameView(player=self.player)
        new_view.message = self.game_message

        msg_content = (
            f"**推演小遊戲** ({self.player.mention})\n"
            f"藍色方塊是起點，**箭頭代表你一開始的面向！**\n"
            f"**步驟：**\n{new_view.rule_display}"
        )

        await self.game_message.edit(content=msg_content, view=new_view)
        await interaction.response.defer()
        await interaction.message.delete()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except:
            pass


class GameView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player
        self.message = None
        self.start_time = time.time()  
        
        self.start_x = random.randint(0, 4)
        self.start_y = random.randint(0, 4)
        self.start_o = random.randint(0, 3) 
        self.o_emojis = {0: '🔼', 1: '▶️', 2: '🔽', 3: '◀️'}

        def move(x, y, o, steps):
            if o == 0: y -= steps   
            elif o == 1: x += steps 
            elif o == 2: y += steps 
            elif o == 3: x -= steps 
            return x % 5, y % 5, o

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
                    
            # 🔥 這裡完完全全照著你的完美邏輯寫的！
            else: 
                text = f"中心點對稱後，前進 {steps} 格"
                def func(x, y, o, st=steps):
                    new_x = (4 - x) % 5
                    new_y = (4 - y) % 5
                    
                    if o == 0 or o == 2:      # 如果是朝上或朝下
                        if new_y == y:        # 目標格的 y = 現在的 y
                            new_o = o         # 方向不變
                        else:                 # 其他狀況 (y變了)
                            new_o = (o + 2) % 4
                            
                    else:                     # 如果是朝左或朝右 (o == 1 or o == 3)
                        if new_x == x:        # 目標格的 x = 現在的 x
                            new_o = o         # 方向不變
                        else:                 # 其他狀況 (x變了)
                            new_o = (o + 2) % 4
                            
                    return move(new_x, new_y, new_o, st)
                return text, func

        self.step_texts = []
        self.step_funcs = []
        
        for _ in range(5):
            text, func = get_action()
            self.step_texts.append(text)
            self.step_funcs.append(func)

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
            seq = random.sample(range(1, 6), 3) 
            macro_text = f"依序執行步驟 {seq[0]}, {seq[1]}, {seq[2]}"
            def macro_func(x, y, o, sequence=seq):
                for s in sequence:
                    x, y, o = self.step_funcs[s-1](x, y, o)
                return x, y, o

        self.step_texts.append(macro_text)
        self.step_funcs.append(macro_func)

        curr_x, curr_y, curr_o = self.start_x, self.start_y, self.start_o
        for func in self.step_funcs:
            curr_x, curr_y, curr_o = func(curr_x, curr_y, curr_o)
            
        self.target_x, self.target_y = curr_x, curr_y
        
        rule_lines = [f"`{i+1}.` {text}" for i, text in enumerate(self.step_texts)]
        self.rule_display = "\n".join(rule_lines)

        for y in range(5):
            for x in range(5):
                btn = GridButton(x, y, self)
                if x == self.start_x and y == self.start_y:
                    btn.style = discord.ButtonStyle.primary
                    btn.label = self.o_emojis[self.start_o]
                self.add_item(btn)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
            if isinstance(child, GridButton) and child.x == self.target_x and child.y == self.target_y:
                child.style = discord.ButtonStyle.success
                child.label = "🎯"
        try:
            if hasattr(self, 'message') and self.message:
                await self.message.edit(content="⏳ **想太久ㄌ! 愚蠢**", view=self)
                post_view = PostGameView(self.player, self.rule_display, self.message)
                post_msg = await self.message.reply(view=post_view)
                post_view.message = post_msg
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

async def setup(bot):
    await bot.add_cog(SpaceLogicGame(bot))