import discord
from discord.ext import commands
from discord import app_commands
import random

# --- 定義網格元素 ---
class Cell:
    def __init__(self, type_name, emoji):
        self.type = type_name
        self.emoji = emoji

# 全域元素表與生成權重
ELEMENTS = {
    "spike1": Cell("spike1", "🦔"),
    "spike2": Cell("spike2", "🦬"),
    "spike4": Cell("spike4", "🦖"),
    "star": Cell("star", "⭐"),
    "shield": Cell("shield", "🛡️"),
    "heal": Cell("heal", "♥️"),
    "coin": Cell("coin", "💰"),
    "portal": Cell("portal", "🌀")
}

def get_random_element():
    # 根據風險與收益設定合理的出現機率
    choices = ["spike1", "spike2", "spike4", "star", "shield", "heal", "coin", "portal"]
    weights = [30, 20, 10, 4, 8, 4, 20, 4]
    return ELEMENTS[random.choices(choices, weights=weights, k=1)[0]]

# --- 遊戲核心引擎 ---
class AncientEngine:
    def __init__(self, player_member):
        self.player = player_member
        self.hp = 9
        self.score = 0
        self.coins = 0
        
        self.invincible_turns = 0
        self.has_shield = False
        self.on_portal = False
        
        # 玩家起始於正中央
        self.px, self.py = 2, 2
        
        # 產生 5x5 初始盤面
        self.grid = [[get_random_element() for _ in range(5)] for _ in range(5)]
        self.grid[self.py][self.px] = "PLAYER" # 覆寫中央為玩家
        
        self.log = "選擇移動方向"

    def resolve_element(self, element, is_invincible=False):
        """處理玩家踩到元素的邏輯"""
        self.on_portal = False # 預設重置傳送門狀態
        
        if element.type.startswith("spike"):
            dmg = int(element.type[-1]) # 擷取傷害值 (1, 2, 4)
            score_gain = dmg
            
            # 使用傳入的 is_invincible 狀態，而不是看現在的 turn 數
            if is_invincible:
                actual_dmg = 0
                self.log = f"單挑ㄌ {element.emoji}！⭐ 無敵狀態擋下 {dmg} 點傷害！積分 +{score_gain}"
            elif self.has_shield:
                actual_dmg = 0
                self.has_shield = False
                self.log = f"單挑ㄌ {element.emoji}！🛡️ 護盾擋下 {dmg} 點傷害！積分 +{score_gain}"
            else:
                actual_dmg = dmg
                self.log = f"單挑ㄌ {element.emoji}！受到 {dmg} 點傷害！積分 +{score_gain}"
                
            self.hp -= actual_dmg
            self.score += score_gain
            
        elif element.type == "star":
            self.invincible_turns = 3
            self.log = "吃ㄌ ⭐ 無敵星星！接下來 3 步免疫傷害"
        elif element.type == "shield":
            self.has_shield = True
            self.log = "拿ㄌ 🛡️ 護盾！免疫下一次傷害"
        elif element.type == "heal":
            old_hp = self.hp
            self.hp = 9
            self.log = f"吃ㄌ ♥️ 回血心！回復 {9 - old_hp} 點生命"
        elif element.type == "coin":
            self.coins += 1
            self.log = "撿ㄌ 💰 金幣"
        elif element.type == "portal":
            self.on_portal = True
            self.log = "走進ㄌ 🌀 傳送門！點擊傳送可傳到另一端"

    def apply_gravity(self):
        """核心重力下落機制 (精準還原範例邏輯)"""
        for x in range(5):
            if self.px == x:
                # 情況 A：玩家在此直排，玩家不可被穿透，會成為掉落物的「阻擋物」
                py = self.py
                
                # 1. 整理玩家下方的元素 (從最底下 y=4 往上收到 py+1)
                below = [self.grid[y][x] for y in range(4, py, -1) if self.grid[y][x] not in (None, "PLAYER")]
                for i, y in enumerate(range(4, py, -1)):
                    if i < len(below):
                        self.grid[y][x] = below[i]
                    else:
                        self.grid[y][x] = None # 沒有東西可掉落，變成空白格
                
                # 2. 整理玩家上方的元素 (從 py-1 往上收到 y=0)
                above = [self.grid[y][x] for y in range(py - 1, -1, -1) if self.grid[y][x] not in (None, "PLAYER")]
                for i, y in enumerate(range(py - 1, -1, -1)):
                    if i < len(above):
                        self.grid[y][x] = above[i]
                    else:
                        self.grid[y][x] = get_random_element() # 頂部生成新元素
            else:
                # 情況 B：玩家不在此直排，所有元素無障礙下落至底部
                elements = [self.grid[y][x] for y in range(4, -1, -1) if self.grid[y][x] not in (None, "PLAYER")]
                for i, y in enumerate(range(4, -1, -1)):
                    if i < len(elements):
                        self.grid[y][x] = elements[i]
                    else:
                        self.grid[y][x] = get_random_element()

    def move(self, dx, dy):
        """處理常規移動"""
        nx, ny = self.px + dx, self.py + dy
        if not (0 <= nx < 5 and 0 <= ny < 5):
            return False # 撞牆

        # 紀錄移動前是否處於無敵狀態，然後再扣除步數
        is_invincible = self.invincible_turns > 0
        if self.invincible_turns > 0:
            self.invincible_turns -= 1

        target = self.grid[ny][nx]
        self.grid[self.py][self.px] = None # 原本位子騰空
        self.px, self.py = nx, ny
        
        if target is not None:
            # 將無敵狀態傳入，確保即使剛扣完變 0，這一步也能擋住傷害
            self.resolve_element(target, is_invincible)
            
        self.grid[self.py][self.px] = "PLAYER"
        self.apply_gravity()
        return True

    def can_teleport(self):
        """檢查版面上是否有另一個傳送門"""
        if not self.on_portal: return False
        for y in range(5):
            for x in range(5):
                if (x != self.px or y != self.py) and self.grid[y][x] and self.grid[y][x].type == "portal":
                    return True
        return False

    def use_portal(self):
        """使用傳送門"""
        portals = []
        for y in range(5):
            for x in range(5):
                if (x != self.px or y != self.py) and self.grid[y][x] and self.grid[y][x].type == "portal":
                    portals.append((x, y))
        
        if not portals: return False
        tx, ty = random.choice(portals)

        # 傳送也算走一步，同樣進行無敵步數扣除
        if self.invincible_turns > 0:
            self.invincible_turns -= 1

        self.grid[self.py][self.px] = None
        self.px, self.py = tx, ty
        
        self.on_portal = False
        self.grid[self.py][self.px] = "PLAYER"
        self.log = f"🌀 傳送到了另一側！"
        
        self.apply_gravity()
        return True

    def render_grid(self):
        """將二維陣列渲染成 Discord 文字方格"""
        num_emojis = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        lines = []
        for y in range(5):
            row_str = ""
            for x in range(5):
                cell = self.grid[y][x]
                if cell == "PLAYER":
                    if self.hp > 0:
                        row_str += f"[{num_emojis[min(9, self.hp)]}]"
                    else:
                        row_str += "[☠️]"
                elif cell is None:
                    row_str += "[⬛]" 
                else:
                    row_str += f"[{cell.emoji}]"
            lines.append(row_str)
        return "\n".join(lines)


# --- UI 操作面板 ---
class AncientGameView(discord.ui.View):
    def __init__(self, engine: AncientEngine, bot):
        super().__init__(timeout=180)
        self.engine = engine
        self.bot = bot

    async def check_user(self, interaction: discord.Interaction):
        if interaction.user != self.engine.player:
            await interaction.response.send_message("不要亂點!", ephemeral=True)
            return False
        return True

    async def update_ui(self, interaction: discord.Interaction):
        if self.engine.hp <= 0:
            await self.end_game(interaction)
        else:
            self.btn_teleport.disabled = not self.engine.can_teleport()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def end_game(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
            
        total_money = self.engine.coins * 10
        economy_cog = self.bot.get_cog("Economy")
        
        if economy_cog and total_money > 0:
            economy_cog.update_balance(self.engine.player.id, total_money)
            self.engine.log = f"**你死ㄌ！**\n共獲取ㄌ {total_money} 元！"
        else:
            self.engine.log = f"**你死ㄌ！**\n得到ㄌ {self.engine.score} 分。"
        await interaction.response.edit_message(embed=self.get_embed(game_over=True), view=self)
        self.stop()

    def get_embed(self, game_over=False):
        embed = discord.Embed(
            title="古老遊戲機", 
            color=discord.Color.red() if game_over else discord.Color.gold()
        )
        
        status = []
        if self.engine.has_shield: status.append("🛡️ 護盾")
        if self.engine.invincible_turns > 0: status.append(f"⭐ 無敵 ({self.engine.invincible_turns}步)")
        status_str = " | ".join(status) if status else "無"

        desc = (
            f"**玩家:** {self.engine.player.mention}\n"
            f"**生命值:** {max(0, self.engine.hp)} / 9\n"
            f"**目前積分:** {self.engine.score} 分\n"
            f"**收集金幣:** {self.engine.coins} 💰 (目前價值 {self.engine.coins * 10} 元)\n"
            f"**目前狀態:** {status_str}\n"
            f"{self.engine.log}\n\n"
            f"{self.engine.render_grid()}"
        )
        
        embed.description = desc
        return embed

    # --- 方向按鈕佈局 ---
    @discord.ui.button(emoji="🌀", style=discord.ButtonStyle.primary, row=0)
    async def btn_teleport(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if self.engine.use_portal():
            await self.update_ui(interaction)

    @discord.ui.button(emoji="⬆️", style=discord.ButtonStyle.secondary, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if not self.engine.move(0, -1):
            return await interaction.response.send_message("撞牆ㄌ！換個方向。", ephemeral=True)
        await self.update_ui(interaction)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if not self.engine.move(-1, 0):
            return await interaction.response.send_message("撞牆ㄌ！換個方向。", ephemeral=True)
        await self.update_ui(interaction)

    @discord.ui.button(emoji="⬇️", style=discord.ButtonStyle.secondary, row=1)
    async def btn_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if not self.engine.move(0, 1):
            return await interaction.response.send_message("撞牆ㄌ！換個方向。", ephemeral=True)
        await self.update_ui(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if not self.engine.move(1, 0):
            return await interaction.response.send_message("撞牆ㄌ！換個方向。", ephemeral=True)
        await self.update_ui(interaction)

# --- 指令註冊區 ---
class AncientGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="遊戲-古老遊戲機", description="挑戰高分及獲得金幣")
    async def start_ancient_game(self, interaction: discord.Interaction):
        engine = AncientEngine(interaction.user)
        view = AncientGameView(engine, self.bot)
        view.btn_teleport.disabled = True # 開局不可能在傳送門上
        
        await interaction.response.send_message(embed=view.get_embed(), view=view)

async def setup(bot):
    await bot.add_cog(AncientGameCog(bot))