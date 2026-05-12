import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from typing import Literal

# --- 遊戲 UI 元件 ---

class GridButton(discord.ui.Button):
    def __init__(self, x, y, view_game):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.view_game = view_game

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user not in self.view_game.players:
            return await interaction.response.send_message("不要亂點！", ephemeral=True)

        elapsed_time = round(time.time() - self.view_game.start_time, 2)
        
        mode = self.view_game.mode
        scores = self.view_game.scores
        players = self.view_game.players
        
        new_streak = self.view_game.streak
        max_streak = self.view_game.max_streak
        penalty = self.view_game.penalty

        # 🔒 絕對時間鎖
        if elapsed_time > 60:
            if mode == "single":
                new_streak = 0
                result_text = f"**超過60秒ㄌ! 愚蠢**\n**(你花了 {elapsed_time} 秒)**\n **連勝沒ㄌ！**\n**最高連勝：{max_streak}**"
            else:
                result_text = f"**超過60秒ㄌ! 都愚蠢**\n**(耗時 {elapsed_time} 秒)**"
                
            grid_str = self.view_game.generate_text_grid(is_timeout=True)
            post_view = PostGameView(players, scores, mode, self.view_game.rule_display, self.view_game.message, new_streak, max_streak, penalty)
            
            await interaction.response.edit_message(content=f"{result_text}\n\n{grid_str}", view=post_view)
            self.view_game.stop()
            return

        # 判斷正確與否
        if self.x == self.view_game.target_x and self.y == self.view_game.target_y:
            # 答對邏輯
            if mode == "single":
                new_streak += 1 
                if new_streak > max_streak:
                    max_streak = new_streak
                result_text = f"**答對ㄌ！**\n**{elapsed_time} 秒**\n**連勝：{new_streak}**\n**最高連勝：{max_streak}**"
            elif mode == "duo":
                scores[user] += 1
                result_text = f"**{user.display_name} 答對ㄌ！**\n**(耗時 {elapsed_time} 秒)**"
            else: # multi
                scores[user] += 1
                result_text = f"**{user.display_name} 答對ㄌ！**\n**(耗時 {elapsed_time} 秒)**"
        else:
            # 答錯邏輯
            if mode == "single":
                new_streak = 0  
                result_text = f"**答錯ㄌ！愚蠢！**\n**想了 {elapsed_time} 秒還錯。**\n**連勝沒ㄌ！**\n**最高連勝：{max_streak}**"
            elif mode == "duo":
                # 雙人模式：點錯的話，對手獲勝
                other_player = players[0] if user == players[1] else players[1]
                scores[other_player] += 1
                result_text = f"**{user.display_name} 答錯ㄌ！** 愚蠢\n**{other_player.display_name} 贏ㄌ！**"
            else: # multi
                # 多人模式：判斷是否要扣分
                if penalty:
                    scores[user] -= 1
                    result_text = f"**{user.display_name} 答錯ㄌ！** 愚蠢 (扣 1 分)"
                else:
                    result_text = f"**{user.display_name} 答錯ㄌ！** 愚蠢"
        
        # 產生文字盤面並替換 View
        grid_str = self.view_game.generate_text_grid(clicked_x=self.x, clicked_y=self.y)
        post_view = PostGameView(players, scores, mode, self.view_game.rule_display, self.view_game.message, new_streak, max_streak, penalty)
        
        await interaction.response.edit_message(content=f"{result_text}\n\n{grid_str}", view=post_view)
        self.view_game.stop()


# =========================================
# 等待加入介面 (雙人/多人專用)
# =========================================
class JoinView(discord.ui.View):
    def __init__(self, host: discord.Member, mode: str):
        super().__init__(timeout=120)
        self.host = host
        self.mode = mode
        self.players = [host]
        self.message = None
        self.penalty = True # 多人模式專用

        # 多人專用的神秘面板 (下拉選單)
        if self.mode == "multi":
            self.settings_select = discord.ui.Select(
                placeholder="計分設定 (預設: 點錯扣分)",
                options=[
                    discord.SelectOption(label="點錯扣分", description="點錯扣分", value="on", default=True),
                    discord.SelectOption(label="點錯不扣分", description="比誰先點對", value="off")
                ],
                row=2
            )
            self.settings_select.callback = self.settings_callback
            self.add_item(self.settings_select)

    async def settings_callback(self, interaction: discord.Interaction):
        if interaction.user != self.host:
            return await interaction.response.send_message("只有房主可以改！", ephemeral=True)
            
        val = self.settings_select.values[0]
        self.penalty = (val == "on")
        
        for opt in self.settings_select.options:
            opt.default = (opt.value == val)
            
        await self.update_ui(interaction)

    async def update_ui(self, interaction: discord.Interaction):
        mode_name = "雙人" if self.mode == "duo" else "多人"
        p_names = ", ".join([p.mention for p in self.players])
        content = f"**{self.host.mention} 發起了推演小遊戲 ({mode_name})！**\n**目前玩家 ({len(self.players)}):** {p_names}\n\n*房主點擊開始！*"
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="加入 / 退出", style=discord.ButtonStyle.secondary, row=1)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            if interaction.user == self.host:
                return await interaction.response.send_message("讓你退ㄌ?", ephemeral=True)
            self.players.remove(interaction.user)
        else:
            if self.mode == "duo" and len(self.players) >= 2:
                return await interaction.response.send_message("滿ㄌ！", ephemeral=True)
            elif self.mode == "multi" and len(self.players) >= 10:
                return await interaction.response.send_message("滿ㄌ (最多10人)！", ephemeral=True)
            
            self.players.append(interaction.user)
        await self.update_ui(interaction)

    @discord.ui.button(label="開始遊戲", style=discord.ButtonStyle.success, row=1)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            return await interaction.response.send_message("只有房主可以開始遊戲！", ephemeral=True)
            
        if len(self.players) < 2:
            return await interaction.response.send_message("至少需要 2 名玩家才能開始！", ephemeral=True)
            
        scores = {p: 0 for p in self.players}
        game_view = GameView(self.players, scores, self.mode, streak=0, max_streak=0, penalty=self.penalty)
        game_view.message = self.message
        
        msg_content = game_view.generate_game_message()
        await interaction.response.edit_message(content=msg_content, view=game_view)
        self.stop()

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(content="**太久ㄌ，不等你們**", view=self)
        except:
            pass


# =========================================
# 結算與控制面板 (負責回看與重開)
# =========================================
class PostGameView(discord.ui.View):
    def __init__(self, players: list, scores: dict, mode: str, rule_display: str, game_message: discord.Message, streak: int = 0, max_streak: int = 0, penalty: bool = True):
        super().__init__(timeout=300)
        self.players = players
        self.scores = scores
        self.mode = mode
        self.rule_display = rule_display
        self.game_message = game_message
        self.streak = streak
        self.max_streak = max_streak
        self.penalty = penalty

        # 雙人/多人模式加入「結算戰績」按鈕
        if self.mode != "single":
            end_btn = discord.ui.Button(label="結算戰績並結束", style=discord.ButtonStyle.danger)
            end_btn.callback = self.end_game
            self.add_item(end_btn)

    @discord.ui.button(label="題目", style=discord.ButtonStyle.secondary)
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{self.rule_display}", ephemeral=True)

    @discord.ui.button(label="再玩", style=discord.ButtonStyle.primary)
    async def restart_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("沒有泥！", ephemeral=True)

        new_view = GameView(self.players, self.scores, self.mode, self.streak, self.max_streak, self.penalty)
        new_view.message = self.game_message

        msg_content = new_view.generate_game_message()
        await interaction.response.edit_message(content=msg_content, view=new_view)
        self.stop()

    async def end_game(self, interaction: discord.Interaction):
        if interaction.user not in self.players:
            return await interaction.response.send_message("沒有泥！", ephemeral=True)
            
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        result_text = "**遊戲結算**\n\n"
        for i, (p, s) in enumerate(sorted_scores):
            result_text += f"**第 {i+1} 名:** {p.display_name}  ({s} 分)\n"
            
        await interaction.response.edit_message(content=result_text, view=None)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            if self.game_message:
                await self.game_message.edit(view=self)
        except:
            pass


# =========================================
# 遊戲核心介面
# =========================================
class GameView(discord.ui.View):
    def __init__(self, players: list, scores: dict, mode: str, streak: int = 0, max_streak: int = 0, penalty: bool = True):
        super().__init__(timeout=60)
        self.players = players
        self.scores = scores
        self.mode = mode
        
        self.streak = streak 
        self.max_streak = max_streak
        self.penalty = penalty
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
                    
            else: 
                text = f"畫面旋轉180°後，前進 {steps} 格"
                def func(x, y, o, st=steps):
                    new_x = (4 - x) % 5
                    new_y = (4 - y) % 5
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

    def generate_game_message(self):
        # 依模式產生分數標頭
        if self.mode == "single":
            score_text = f"**連勝：{self.streak}**\n**最高連勝：{self.max_streak}**"
        elif self.mode == "duo":
            p1, p2 = self.players[0], self.players[1]
            score_text = f"**{p1.display_name} : {self.scores[p1]} 勝** |  **{p2.display_name} : {self.scores[p2]} 勝**"
        else:
            sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
            top_3 = sorted_scores[:3]
            score_text = "**領先：**\n"
            for i, (p, s) in enumerate(top_3):
                score_text += f"{i+1}. {p.display_name} ({s} 分)   "

        mode_titles = {"single": "單人", "duo": "雙人", "multi": "多人"}
        
        return (
            f"**推演小遊戲 ({mode_titles[self.mode]}模式)**\n"
            f"{score_text}\n" 
            f"藍色方塊是起點，**箭頭代表你一開始的面向！**\n"
            f"**步驟：**\n{self.rule_display}"
        )

    def generate_text_grid(self, clicked_x=None, clicked_y=None, is_timeout=False):
        grid_str = ""
        for y in range(5):
            for x in range(5):
                if x == self.target_x and y == self.target_y:
                    grid_str += "☑️" 
                elif not is_timeout and clicked_x is not None and clicked_y is not None and x == clicked_x and y == clicked_y:
                    grid_str += "❌" 
                elif x == self.start_x and y == self.start_y:
                    grid_str += self.o_emojis[self.start_o] 
                else:
                    grid_str += "⬛" 
            grid_str += "\n"
        return grid_str

    async def on_timeout(self):
        try:
            if hasattr(self, 'message') and self.message:
                grid_str = self.generate_text_grid(is_timeout=True)
                
                if self.mode == "single":
                    text = f"**想太久ㄌ! 愚蠢**\n **連勝中斷！**\n **最高連勝：{self.max_streak}**"
                else:
                    text = f"**想太久ㄌ! 都愚蠢**"
                    
                post_view = PostGameView(self.players, self.scores, self.mode, self.rule_display, self.message, streak=0, max_streak=self.max_streak, penalty=self.penalty)
                await self.message.edit(content=f"{text}\n\n{grid_str}", view=post_view)
        except:
            pass


# --- Cog 註冊 ---

class SpaceLogicGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gridgame", description="推演小遊戲")
    @app_commands.describe(mode="選擇模式 (預設單人)")
    async def play_game(self, interaction: discord.Interaction, mode: Literal["單人", "雙人", "多人"] = "單人"):
        
        mode_map = {"單人": "single", "雙人": "duo", "多人": "multi"}
        selected_mode = mode_map[mode]

        if selected_mode == "single":
            # 單人直接開局
            scores = {interaction.user: 0}
            view = GameView([interaction.user], scores, "single", streak=0, max_streak=0)
            msg_content = view.generate_game_message()
            await interaction.response.send_message(content=msg_content, view=view)
            view.message = await interaction.original_response()
        else:
            # 雙人或多人，跳出乾淨的等候加入區
            view = JoinView(host=interaction.user, mode=selected_mode)
            mode_name = "雙人" if selected_mode == "duo" else "多人"
            content = f"**{interaction.user.mention} 的 ({mode_name})！**\n**目前玩家 (1):** {interaction.user.mention}\n\n*發起人點擊開始*"
            await interaction.response.send_message(content=content, view=view)
            view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(SpaceLogicGame(bot))