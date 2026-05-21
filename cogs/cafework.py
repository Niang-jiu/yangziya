import discord
from discord.ext import commands
from discord import app_commands
import random

# --- 遊戲狀態管理 ---
class CafeState:
    def __init__(self, user: discord.Member):
        self.user = user
        self.profit = 0
        self.insurance_cards = 0
        self.turn = 1
        self.max_turns = 10
        self.slime_weight = 1
        self.log_message = "開店ㄌ"
        
        self.current_customer = ""
        self.current_cups = 0
        
        # --- 新增：拒絕次數管理 ---
        self.reject_count = 0
        self.max_rejects = 5
        
    def generate_customer(self):
        customers = ["骷髏", "史萊姆", "哥布林", "乞丐", "富人", "強盜"]
        
        # 怪物權重保持不變，將一般人權重提升至 5
        # 初始總權重為 18，怪物出現機率為 1/18 (精準達到原本 1/6 的三分之一)
        weights = [1, self.slime_weight, 1, 3, 3, 3]
        
        self.current_customer = random.choices(customers, weights=weights, k=1)[0]
        
        if self.current_customer in ["富人", "強盜"]:
            self.current_cups = 1
        else:
            self.current_cups = random.randint(1, 5)

    def handle_attack(self):
        if self.insurance_cards > 0:
            self.insurance_cards -= 1
            self.profit -= 20
            return "對方生氣地把你打了一頓！有健保，付ㄌ醫藥費 20 元"
        else:
            self.profit -= 200
            return "對方生氣地把你打了一頓！沒有健保，賠ㄌ醫藥費 200 元"

    def sell(self):
        cost = self.current_cups * 10
        self.profit -= cost
        revenue = 0
        msg = ""

        if self.current_customer == "骷髏":
            msg = f"骷髏喝了霸王咖啡，全不付錢。(虧ㄌ {cost} 元)"
        elif self.current_customer == "史萊姆":
            revenue = self.current_cups * 5
            msg = f"史萊姆每杯付了 5 元，共收 {revenue} 元。(成本 {cost} 元)"
        elif self.current_customer == "哥布林":
            pay_per_cup = random.randint(3, 7)
            revenue = self.current_cups * pay_per_cup
            msg = f"哥布林每杯付了 {pay_per_cup} 元，共收 {revenue} 元。(成本 {cost} 元)"
        elif self.current_customer == "乞丐":
            pay_per_cup = random.randint(0, 30)
            revenue = self.current_cups * pay_per_cup
            msg = f"乞丐每杯付了 {pay_per_cup} 元，共收 {revenue} 元。(成本 {cost} 元)"
        elif self.current_customer == "富人":
            roll = random.random()
            if roll < 0.0001:
                revenue = 1000
            elif roll < 0.10:
                revenue = 50
            else:
                revenue = 10
            msg = f"富人付了 {revenue} 元。(成本 {cost} 元)"
        elif self.current_customer == "強盜":
            if random.choice([True, False]):
                revenue = 30
                msg = f"強盜付了 30 元。(成本 {cost} 元)"
            else:
                self.profit -= 30
                msg = f"強盜不付錢，還搶走你 30 元！(虧ㄌ {cost + 30} 元)"

        self.profit += revenue
        return msg

    def reject(self):
        msg = f"你拒絕ㄌ {self.current_customer}。"
        if self.current_customer == "骷髏":
            if random.random() < 0.3:
                msg += " " + self.handle_attack()
            else:
                msg += " 他低頭傷心ㄉ走了"
        elif self.current_customer == "史萊姆":
            self.slime_weight *= 3
            msg += " 史萊姆瘋狂分裂。之後出現率翻3倍)"
        elif self.current_customer == "哥布林":
            if random.random() < 0.5:
                msg += " " + self.handle_attack()
            else:
                msg += " 他低頭傷心ㄉ走了"
        else:
            msg += " 他哭著傷心ㄉ走了"
            
        return msg

    def get_display_text(self):
        # 使用 min 確保顯示的回合數不會超過 max_turns (避免 11 / 10 的情況)
        display_turn = min(self.turn, self.max_turns)
        
        display = (
            f"第 {display_turn} / {self.max_turns} 位客人\n"
            f"目前總利潤：{self.profit} 元\n"
            f"健保卡剩餘：{self.insurance_cards} 張\n"
            f"剩餘拒絕次數：{self.max_rejects - self.reject_count} 次\n"
            "--------------------------\n"
            f"上回動態：{self.log_message}\n\n"
        )
        
        if self.turn <= self.max_turns:
            display += (
                f"來ㄌ一位客人：{self.current_customer}\n"
                f"對方要求購買 {self.current_cups} 杯咖啡。\n"
                f"(若售出，將扣除成本 {self.current_cups * 10} 元)"
            )
        else:
            display += "營業結束"
            
        return display


# --- 第二階段：遊戲主操作面板 ---
class CafeGameView(discord.ui.View):
    def __init__(self, state: CafeState, bot):
        super().__init__(timeout=120)
        self.state = state
        self.bot = bot

    async def check_user(self, interaction: discord.Interaction):
        if interaction.user != self.state.user:
            await interaction.response.send_message("自己去打工", ephemeral=True)
            return False
        return True

    async def update_game(self, interaction: discord.Interaction):
        self.state.turn += 1
        
        if self.state.turn > self.state.max_turns:
            # 遊戲結束，進入結算
            await self.end_game(interaction)
        else:
            # 繼續下一回合
            self.state.generate_customer()
            await interaction.response.edit_message(content=self.state.get_display_text(), view=self)

    async def end_game(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True

        final_msg = self.state.get_display_text() + "\n\n"
        
        if self.state.profit > 0:
            economy_cog = self.bot.get_cog("Economy")
            if economy_cog:
                economy_cog.update_balance(self.state.user.id, self.state.profit)
                final_msg += f"賺ㄌ {self.state.profit} 元"
            else:
                final_msg += f"賺ㄌ {self.state.profit} 元 (但找不到經濟系統)。"
        else:
            final_msg += f"總利潤為 {self.state.profit} 元。被開除ㄌ"

        await interaction.response.edit_message(content=final_msg, view=self)
        self.stop()

    @discord.ui.button(label="給他", style=discord.ButtonStyle.success)
    async def btn_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        self.state.log_message = self.state.sell()
        await self.update_game(interaction)

    @discord.ui.button(label="拒絕", style=discord.ButtonStyle.danger)
    async def btn_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        
        # 檢查拒絕次數是否已達上限
        if self.state.reject_count >= self.state.max_rejects:
            await interaction.response.send_message("拒絕次數已達上限 (5次)", ephemeral=True)
            return
            
        # 紀錄拒絕次數並執行拒絕邏輯
        self.state.reject_count += 1
        self.state.log_message = self.state.reject()
        
        # 如果這次拒絕完剛好用光次數，就把按鈕禁用
        if self.state.reject_count >= self.state.max_rejects:
            button.disabled = True
            
        await self.update_game(interaction)


# --- 第一階段：購買健保面板 ---
class InsuranceView(discord.ui.View):
    def __init__(self, state: CafeState, bot):
        super().__init__(timeout=60)
        self.state = state
        self.bot = bot

    async def check_user(self, interaction: discord.Interaction):
        if interaction.user != self.state.user:
            await interaction.response.send_message("自己去打工", ephemeral=True)
            return False
        return True

    async def start_game(self, interaction: discord.Interaction, amount: int):
        cost = amount * 30
        self.state.insurance_cards = amount
        self.state.profit -= cost
        self.state.log_message = f"花ㄌ {cost} 元買 {amount} 張健保卡。"
    
        self.state.generate_customer()
        game_view = CafeGameView(self.state, self.bot)
        await interaction.response.edit_message(content=self.state.get_display_text(), view=game_view)
        self.stop()

    @discord.ui.button(label="不買 (0元)", style=discord.ButtonStyle.secondary)
    async def btn_0(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        await self.start_game(interaction, 0)

    @discord.ui.button(label="買 1 張 (30元)", style=discord.ButtonStyle.primary)
    async def btn_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        await self.start_game(interaction, 1)

    @discord.ui.button(label="買 2 張 (60元)", style=discord.ButtonStyle.primary)
    async def btn_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        await self.start_game(interaction, 2)

    @discord.ui.button(label="買 3 張 (90元)", style=discord.ButtonStyle.primary)
    async def btn_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        await self.start_game(interaction, 3)


# --- Cog 指令註冊區 ---
class CafeWork(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="工作-咖啡廳", description="咖啡廳打工")
    @app_commands.describe(介紹="遊戲介紹")
    @app_commands.checks.cooldown(1, 120, key=lambda i: i.user.id)
    async def start_cafe(self, interaction: discord.Interaction, 介紹: bool = False):
        if 介紹:
            
            intro_text = (
                "# 咖啡廳打工\n"
                "共10 位客人，每杯咖啡成本 10 元\n"
                "共5 次拒絕客人的機會\n\n"
                
                "**健保卡與醫藥費**\n"
                "每張健保卡售價 30 元\n"
                "若拒絕客人遭到攻擊：\n"
                "無健保：醫藥費 200 元\n"
                "有健保：消耗 1 張健保卡，醫藥費降為 20 元。\n\n"
                
                "圖鑑\n"
                "**骷髏** (出現機率 1/12) - 買 1~5 杯\n"
                "不付錢\n"
                "拒絕：30% 機率打人\n\n"
                
                "**史萊姆** (出現機率 1/12) - 買 1~5 杯\n"
                "每杯固定付 5 元\n"
                "拒絕：之後出現率翻 3 倍\n\n"
                
                "* 哥布林(出現機率 1/12) - 買 1~5 杯\n"
                "每杯隨機付 3~7 元(同個人每杯都付同樣價錢)\n"
                "拒絕：50% 機率打人。\n\n"
                
                "**乞丐** (出現機率 3/12) - 買 1~5 杯\n"
                "隨機付 0~30 元(同個人每杯都付同樣價錢)\n"
                "拒絕：沒事\n\n"
                
                "**富人** (出現機率 3/12) - 固定買 1 杯\n"
                "90% 付 10 元，9.99% 付 50 元，0.01% 機率付 1000 元\n"
                "拒絕：沒事\n\n"
                
                "**強盜** (出現機率 3/12) - 固定買 1 杯\n"
                " 50%付 30 元，50% 搶走 30 元且賠咖啡成本\n"
                "拒絕：沒事"
            )
            await interaction.response.send_message(content=intro_text, ephemeral=True)
            return

        # 正常遊戲邏輯
        state = CafeState(interaction.user)
        view = InsuranceView(state, self.bot)
        
        intro_text = (
            "要買幾張健保卡。\n"
            "每張 30 元。被打後，有健保卡可將 200 元醫藥費降為 20 元 (並消耗一張)。"
        )
        await interaction.response.send_message(content=intro_text, view=view)

    @start_cafe.error
    async def on_cafe_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"咖啡廳還在打掃，請等待 {int(error.retry_after)} 秒後再來", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CafeWork(bot))