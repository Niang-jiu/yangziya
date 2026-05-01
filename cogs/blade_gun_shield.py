import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# --- 遊戲核心邏輯 ---

class Player:
    def __init__(self, user: discord.Member, x: int, y: int):
        self.user = user
        self.hp = 10
        self.x = x
        self.y = y
        self.has_damage_buff = False
        self.cards = ["刀", "槍", "盾"]
        
        self.selected_card = None
        self.target_x = x
        self.target_y = y
        
        self.is_shielded = False
        self.facing = None 
        self.action_submitted = False

class BGSGameEngine:
    def __init__(self, player1: Player, player2: Player):
        self.board_size = 10
        self.p1 = player1
        self.p2 = player2
        self.turn_count = 1

    def get_relative_target(self, card: str, current_x: int, current_y: int, direction: int, distance: int = 1):
        """將玩家輸入的方向編號轉換為實際座標"""
        if card == "刀":
            mapping = {1: (1, -2), 2: (2, -1), 3: (2, 1), 4: (1, 2), 5: (-1, 2), 6: (-2, 1), 7: (-2, -1), 8: (-1, -2)}
            if direction not in mapping: return None
            dx, dy = mapping[direction]
            return current_x + dx, current_y + dy
            
        elif card == "盾":
            mapping = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, 1), 5: (-1, 1), 6: (-1, 0), 7: (-1, -1), 8: (0, -1)}
            if direction not in mapping: return None
            dx, dy = mapping[direction]
            return current_x + dx, current_y + dy
            
        elif card == "槍":
            mapping = {1: (0, 1), 2: (1, 0), 3: (-1, 0), 4: (0, -1)}
            if direction not in mapping: return None
            dx, dy = mapping[direction]
            return current_x + (dx * distance), current_y + (dy * distance)
            
        return None

    def validate_and_set_action(self, player: Player, card: str, direction: int, distance: int = 1):
        """驗證並設定玩家行動"""
        target = self.get_relative_target(card, player.x, player.y, direction, distance)
        
        if not target:
            return False, "方向輸入錯誤！"
            
        tx, ty = target
        if tx < 0 or tx >= self.board_size or ty < 0 or ty >= self.board_size:
            return False, "超出邊界了！撞牆啦！"

        player.selected_card = card
        player.target_x = tx
        player.target_y = ty
        player.action_submitted = True
        
        dx = player.target_x - player.x
        dy = player.target_y - player.y
        
        if card == "刀":
            if abs(dy) > abs(dx):
                player.facing = "UP" if dy < 0 else "DOWN"
            else:
                player.facing = "LEFT" if dx < 0 else "RIGHT"
                
        return True, ""

    def render_board(self):
        """產生 10x10 棋盤"""
        board = [["🔲" for _ in range(self.board_size)] for _ in range(self.board_size)]
        if self.p1.x == self.p2.x and self.p1.y == self.p2.y:
            board[self.p1.y][self.p1.x] = "💥"
        else:
            board[self.p1.y][self.p1.x] = "🟦"
            board[self.p2.y][self.p2.x] = "🟥"
            
        display = ""
        for row in board:
            display += "".join(row) + "\n"
        return display

    def resolve_turn(self):
        log = [f"**【第 {self.turn_count} 回合結算】**"]
        
        p1_t = (self.p1.target_x, self.p1.target_y)
        p2_t = (self.p2.target_x, self.p2.target_y)

        # 1. 衝突判定
        if p1_t == p2_t:
            log.append("💥 **雙方目標為同一格，觸發近距離廝殺！卡牌效果全部失效！**")
            self.p1.x, self.p1.y = p1_t
            self.p2.x, self.p2.y = p2_t
            return self._resolve_clash(log)

        # 2. 刀、盾移動
        for p in [self.p1, self.p2]:
            if p.selected_card in ["刀", "盾"]:
                p.x, p.y = p.target_x, p.target_y
                name_display = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                if p.selected_card == "盾":
                    p.is_shielded = True
                    log.append(f"🛡️ {name_display} 舉起盾牌，移動至 ({p.x}, {p.y})")
                else:
                    log.append(f"🗡️ {name_display} 拔刀跳躍，移動至 ({p.x}, {p.y})")

        # 3. 槍移動與對衝
        self._resolve_gun_movement(log)

        # 4. 攻擊與反彈
        self._resolve_attacks(log)

        return self._end_turn(log)

    def _resolve_clash(self, log: list):
        p1_dmg = 10 if self.p1.has_damage_buff else 5
        p2_dmg = 10 if self.p2.has_damage_buff else 5
        
        self.p1.hp -= p2_dmg
        self.p2.hp -= p1_dmg
        
        p1_name = self.p1.user.display_name if self.p1.user != self.p2.user else "玩家1"
        p2_name = self.p2.user.display_name if self.p1.user != self.p2.user else "玩家2"
                
        log.append(f"🩸 廝殺結果：\n🟦 {p1_name} 剩餘血量: {self.p1.hp}\n🟥 {p2_name} 剩餘血量: {self.p2.hp}")
        return self._end_turn(log)

    def _resolve_gun_movement(self, log: list):
        p1_gun = self.p1.selected_card == "槍"
        p2_gun = self.p2.selected_card == "槍"

        if p1_gun and p2_gun and self._is_path_crossing():
            log.append("🔥 **雙方持槍對衝！互相穿透並造成 4 點傷害！**")
            self.p1.hp -= 4
            self.p2.hp -= 4
            self.p1.x, self.p1.y = self.p1.target_x, self.p1.target_y
            self.p2.x, self.p2.y = self.p2.target_x, self.p2.target_y
            return

        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            if p.selected_card == "槍":
                dx = 1 if p.target_x > p.x else (-1 if p.target_x < p.x else 0)
                dy = 1 if p.target_y > p.y else (-1 if p.target_y < p.y else 0)
                
                curr_x, curr_y = p.x, p.y
                hit = False
                
                while (curr_x, curr_y) != (p.target_x, p.target_y):
                    curr_x += dx
                    curr_y += dy
                    if curr_x == enemy.x and curr_y == enemy.y:
                        hit = True
                        p.x = curr_x - dx if dx != 0 else curr_x
                        p.y = curr_y - dy if dy != 0 else curr_y
                        p_name = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                        log.append(f"🎯 {p_name} 衝刺撞到對手，緊急煞車於 ({p.x}, {p.y})")
                        break
                
                if not hit:
                    p.x, p.y = p.target_x, p.target_y
                    p_name = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                    log.append(f"💨 {p_name} 持槍衝刺至 ({p.x}, {p.y})")

    def _is_path_crossing(self):
        if self.p1.y == self.p2.y and self.p1.target_y == self.p2.target_y:
            if min(self.p1.x, self.p1.target_x) <= max(self.p2.x, self.p2.target_x) and \
               max(self.p1.x, self.p1.target_x) >= min(self.p2.x, self.p2.target_x):
                return True
        if self.p1.x == self.p2.x and self.p1.target_x == self.p2.target_x:
            if min(self.p1.y, self.p1.target_y) <= max(self.p2.y, self.p2.target_y) and \
               max(self.p1.y, self.p1.target_y) >= min(self.p2.y, self.p2.target_y):
                return True
        return False

    def _resolve_attacks(self, log: list):
        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            dmg = 0
            if p.selected_card == "刀":
                in_range = False
                if p.facing == "UP" and p.y - 2 <= enemy.y < p.y and abs(enemy.x - p.x) <= 1: in_range = True
                elif p.facing == "DOWN" and p.y < enemy.y <= p.y + 2 and abs(enemy.x - p.x) <= 1: in_range = True
                elif p.facing == "LEFT" and p.x - 2 <= enemy.x < p.x and abs(enemy.y - p.y) <= 1: in_range = True
                elif p.facing == "RIGHT" and p.x < enemy.x <= p.x + 2 and abs(enemy.y - p.y) <= 1: in_range = True
                if in_range: dmg = 2
                    
            elif p.selected_card == "槍":
                dist = abs(enemy.x - p.x) + abs(enemy.y - p.y)
                if (enemy.x == p.x or enemy.y == p.y) and dist == 1:
                    dmg = 4

            if dmg > 0:
                p_name = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                e_name = enemy.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if enemy == self.p1 else '2'}"
                
                if enemy.is_shielded:
                    reflect = int(dmg * 0.5)
                    p.hp -= reflect
                    log.append(f"🛡️ {e_name} 的盾牌反彈了攻擊！{p_name} 受到 {reflect} 點反傷！")
                else:
                    enemy.hp -= dmg
                    log.append(f"⚔️ {p_name} 命中了！對 {e_name} 造成 {dmg} 點傷害！")

    def _end_turn(self, log: list):
        p1_name = self.p1.user.display_name if self.p1.user != self.p2.user else "玩家1"
        p2_name = self.p2.user.display_name if self.p1.user != self.p2.user else "玩家2"
        
        if self.p1.hp <= 0 and self.p2.hp <= 0:
            log.append("\n💀 **雙方同時倒下，遊戲平手！**")
            return {"status": "over", "log": log}
        elif self.p1.hp <= 0:
            log.append(f"\n🏆 **{p2_name} 獲得勝利！**")
            return {"status": "over", "log": log}
        elif self.p2.hp <= 0:
            log.append(f"\n🏆 **{p1_name} 獲得勝利！**")
            return {"status": "over", "log": log}

        self.p1.cards.remove(self.p1.selected_card)
        self.p1.cards.append(random.choice(["刀", "槍", "盾"]))
        self.p2.cards.remove(self.p2.selected_card)
        self.p2.cards.append(random.choice(["刀", "槍", "盾"]))
        
        self.p1.action_submitted = False
        self.p2.action_submitted = False
        self.p1.is_shielded = False
        self.p2.is_shielded = False
        self.turn_count += 1
        return {"status": "continue", "log": log}


# --- Discord UI 介面 ---

class DirBtn(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label=str(direction), style=discord.ButtonStyle.primary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        is_valid, msg = view.main_view.engine.validate_and_set_action(view.player, view.card, self.direction)
        
        if not is_valid:
            await interaction.response.send_message(f"❌ 錯誤：{msg}", ephemeral=True)
            return
            
        await interaction.response.edit_message(content="✅ 行動鎖定完成！等待對手...", view=None)
        await view.main_view.check_turn_ready()


class DirectionViewBlade(discord.ui.View):
    def __init__(self, player, card, main_view):
        super().__init__(timeout=60)
        self.player = player
        self.card = card
        self.main_view = main_view
        
        # 明確分行，保證 5x5 排版不跑版
        layout = [
            [None, 8, None, 1, None],
            [7, None, None, None, 2],
            [None, None, "🗡️", None, None],
            [6, None, None, None, 3],
            [None, 5, None, 4, None]
        ]
        
        for r_idx, row in enumerate(layout):
            for item in row:
                if isinstance(item, int):
                    self.add_item(DirBtn(item, row=r_idx))
                elif item == "🗡️":
                    btn = discord.ui.Button(label="\u200b", emoji="🗡️", disabled=True, style=discord.ButtonStyle.gray, row=r_idx)
                    self.add_item(btn)
                else:
                    btn = discord.ui.Button(label="\u200b", disabled=True, style=discord.ButtonStyle.gray, row=r_idx)
                    self.add_item(btn)

class DirectionViewShield(discord.ui.View):
    def __init__(self, player, card, main_view):
        super().__init__(timeout=60)
        self.player = player
        self.card = card
        self.main_view = main_view
        
        # 明確分行，保證 3x3 盾牌不跑版
        layout = [
            [7, 8, 1],
            [6, "🛡️", 2],
            [5, 4, 3]
        ]
        for r_idx, row in enumerate(layout):
            for item in row:
                if isinstance(item, int):
                    self.add_item(DirBtn(item, row=r_idx))
                else:
                    btn = discord.ui.Button(label="\u200b", emoji="🛡️", disabled=True, style=discord.ButtonStyle.gray, row=r_idx)
                    self.add_item(btn)

class GunDistanceModal(discord.ui.Modal, title='設定槍的衝刺'):
    dir_input = discord.ui.TextInput(
        label='方向 (上4, 右2, 下1, 左3)',
        placeholder='輸入 1~4',
        required=True,
        max_length=1
    )
    dist_input = discord.ui.TextInput(
        label='衝刺距離 (1-9)',
        placeholder='輸入 1~9',
        required=True,
        max_length=1
    )

    def __init__(self, player, card, main_view):
        super().__init__()
        self.player = player
        self.card = card
        self.main_view = main_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.dir_input.value)
            dist = int(self.dist_input.value)
            if d not in [1, 2, 3, 4] or dist < 1 or dist > 9:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("輸入格式錯誤！方向需為 1~4，距離需為 1~9。", ephemeral=True)
            return

        is_valid, msg = self.main_view.engine.validate_and_set_action(self.player, self.card, d, dist)
        if not is_valid:
            await interaction.response.send_message(f"❌ 無效行動：{msg}", ephemeral=True)
            return

        await interaction.response.edit_message(content="✅ 行動鎖定完成！等待對手...", view=None)
        await self.main_view.check_turn_ready()


class CardButton(discord.ui.Button):
    def __init__(self, card_name):
        super().__init__(label=f"出 {card_name}", style=discord.ButtonStyle.secondary)
        self.card_name = card_name

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if self.card_name == "刀":
            await interaction.response.edit_message(content=f"{view.title_prefix} 準備出【刀】\n請點擊你要跳躍的位置 (對應數字盤):", view=DirectionViewBlade(view.player, self.card_name, view.main_view))
        elif self.card_name == "盾":
            await interaction.response.edit_message(content=f"{view.title_prefix} 準備出【盾】\n請點擊你要防禦的位置 (對應數字盤):", view=DirectionViewShield(view.player, self.card_name, view.main_view))
        elif self.card_name == "槍":
            await interaction.response.send_modal(GunDistanceModal(view.player, self.card_name, view.main_view))

class CardSelectView(discord.ui.View):
    def __init__(self, player: Player, main_view, title_prefix):
        super().__init__(timeout=60)
        self.player = player
        self.main_view = main_view
        self.title_prefix = title_prefix

        # 動態產生手牌按鈕，避免重複選項
        for card in set(self.player.cards): 
            self.add_item(CardButton(card))


class BGSMainView(discord.ui.View):
    def __init__(self, engine: BGSGameEngine):
        super().__init__(timeout=None)
        self.engine = engine
        self.message = None

    @discord.ui.button(label="P1 決定行動", style=discord.ButtonStyle.primary, custom_id="bgs_action_p1")
    async def p1_action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.engine.p1.user:
            await interaction.response.send_message("你不是 🟦 玩家1！", ephemeral=True)
            return
        if self.engine.p1.action_submitted:
            await interaction.response.send_message("你已經決定過行動了！", ephemeral=True)
            return
        await interaction.response.send_message("請選擇要出的牌：", view=CardSelectView(self.engine.p1, self, "🟦 P1 "), ephemeral=True)

    @discord.ui.button(label="P2 決定行動", style=discord.ButtonStyle.danger, custom_id="bgs_action_p2")
    async def p2_action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.engine.p2.user:
            await interaction.response.send_message("你不是 🟥 玩家2！", ephemeral=True)
            return
        if self.engine.p2.action_submitted:
            await interaction.response.send_message("你已經決定過行動了！", ephemeral=True)
            return
        await interaction.response.send_message("請選擇要出的牌：", view=CardSelectView(self.engine.p2, self, "🟥 P2 "), ephemeral=True)

    async def check_turn_ready(self):
        if self.engine.p1.action_submitted and self.engine.p2.action_submitted:
            res = self.engine.resolve_turn()
            
            p1_name = self.engine.p1.user.display_name if self.engine.p1.user != self.engine.p2.user else "玩家1"
            p2_name = self.engine.p2.user.display_name if self.engine.p1.user != self.engine.p2.user else "玩家2"
            
            log_text = "\n".join(res["log"])
            board_display = self.engine.render_board()
            
            status_text = (
                f"\n{board_display}\n"
                f"🟦 **[{p1_name}]** HP: {self.engine.p1.hp} | 座標: ({self.engine.p1.x}, {self.engine.p1.y}) | 手牌: {', '.join(self.engine.p1.cards)}\n"
                f"🟥 **[{p2_name}]** HP: {self.engine.p2.hp} | 座標: ({self.engine.p2.x}, {self.engine.p2.y}) | 手牌: {', '.join(self.engine.p2.cards)}"
            )
            
            if res["status"] == "over":
                for child in self.children:
                    child.disabled = True
                await self.message.edit(content=log_text + status_text, view=self)
            else:
                await self.message.edit(content=log_text + status_text, view=self)

class BladeGunShieldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bgs", description="發起一場刀槍盾對決！(選自己可以單人雙排測試)")
    async def start_bgs(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("對不起鴨，我不會玩", ephemeral=True)
            return
        
        p1 = Player(interaction.user, 0, 0)
        p2 = Player(opponent, 9, 9)
        engine = BGSGameEngine(p1, p2)
        view = BGSMainView(engine)
        
        p1_name = p1.user.mention if p1.user != p2.user else "玩家1 (你)"
        p2_name = p2.user.mention if p1.user != p2.user else "玩家2 (也是你)"
        
        board_display = engine.render_board()
        
        msg = (
            f"⚔️ **《刀槍盾》生死鬥開始！** ⚔️\n"
            f"🟦 {p1_name} VS 🟥 {p2_name}\n"
            f"滿血皆為 10 點。請點擊下方按鈕盲出你的牌與目標座標！\n\n"
            f"{board_display}\n"
            f"🟦 **[P1]** 手牌: {', '.join(p1.cards)}\n"
            f"🟥 **[P2]** 手牌: {', '.join(p2.cards)}"
        )
        
        await interaction.response.send_message(msg, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))