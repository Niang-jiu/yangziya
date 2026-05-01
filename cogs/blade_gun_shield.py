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

    def set_action(self, player: Player, card: str, tx: int, ty: int):
        """設定玩家行動"""
        player.selected_card = card
        player.target_x = max(0, min(self.board_size - 1, tx))
        player.target_y = max(0, min(self.board_size - 1, ty))
        player.action_submitted = True
        
        dx = player.target_x - player.x
        dy = player.target_y - player.y
        
        # 決定刀的面向
        if card == "刀":
            if abs(dy) > abs(dx):
                player.facing = "UP" if dy < 0 else "DOWN"
            else:
                player.facing = "LEFT" if dx < 0 else "RIGHT"

    def resolve_turn(self):
        """完整回合結算"""
        log = [f"**【第 {self.turn_count} 回合結算】**"]
        
        p1_t = (self.p1.target_x, self.p1.target_y)
        p2_t = (self.p2.target_x, self.p2.target_y)

        # 1. 最高優先級：同格碰撞 (近距離廝殺)
        if p1_t == p2_t:
            log.append("💥 **雙方目標為同一格，觸發近距離廝殺！卡牌效果全部失效！**")
            self.p1.x, self.p1.y = p1_t
            self.p2.x, self.p2.y = p2_t
            return self._resolve_clash(log)

        # 2. 移動階段上：刀、盾先走
        for p in [self.p1, self.p2]:
            if p.selected_card in ["刀", "盾"]:
                p.x, p.y = p.target_x, p.target_y
                if p.selected_card == "盾":
                    p.is_shielded = True
                    # 單人測試時，用 P1/P2 區分
                    name_display = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                    log.append(f"🛡️ {name_display} 舉起盾牌，移動至 ({p.x}, {p.y})")
                else:
                    name_display = p.user.display_name if self.p1.user != self.p2.user else f"玩家{'1' if p == self.p1 else '2'}"
                    log.append(f"🗡️ {name_display} 拔刀跳躍，移動至 ({p.x}, {p.y})")

        # 3. 移動階段下：槍的移動與對衝
        self._resolve_gun_movement(log)

        # 4. 結算一般攻擊與盾牌反彈
        self._resolve_attacks(log)

        # 5. 檢查勝負與回合結束
        return self._end_turn(log)

    def _resolve_clash(self, log: list):
        p1_dmg = 10 if self.p1.has_damage_buff else 5
        p2_dmg = 10 if self.p2.has_damage_buff else 5
        
        self.p1.hp -= p2_dmg
        self.p2.hp -= p1_dmg
        
        p1_name = self.p1.user.display_name if self.p1.user != self.p2.user else "玩家1"
        p2_name = self.p2.user.display_name if self.p1.user != self.p2.user else "玩家2"
                
        log.append(f"🩸 廝殺結果：\n{p1_name} 剩餘血量: {self.p1.hp}\n{p2_name} 剩餘血量: {self.p2.hp}")
        return self._end_turn(log)

    def _resolve_gun_movement(self, log: list):
        p1_gun = self.p1.selected_card == "槍"
        p2_gun = self.p2.selected_card == "槍"

        # 特例：對衝
        if p1_gun and p2_gun and self._is_path_crossing():
            log.append("🔥 **雙方持槍對衝！互相穿透並造成 4 點傷害！**")
            self.p1.hp -= 4
            self.p2.hp -= 4
            self.p1.x, self.p1.y = self.p1.target_x, self.p1.target_y
            self.p2.x, self.p2.y = self.p2.target_x, self.p2.target_y
            return

        # 一般槍衝刺
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
            log.append("💀 **雙方同時倒下，遊戲平手！**")
            return {"status": "over", "log": log}
        elif self.p1.hp <= 0:
            log.append(f"🏆 **{p2_name} 獲得勝利！**")
            return {"status": "over", "log": log}
        elif self.p2.hp <= 0:
            log.append(f"🏆 **{p1_name} 獲得勝利！**")
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

class ActionModal(discord.ui.Modal):
    def __init__(self, player: Player, view, title_prefix=""):
        super().__init__(title=f'{title_prefix}選擇行動')
        self.player = player
        self.parent_view = view
        
        self.card_input = discord.ui.TextInput(
            label='出牌 (刀/槍/盾)',
            placeholder=f'可用手牌: {", ".join(self.player.cards)}',
            required=True,
            max_length=1
        )
        self.x_input = discord.ui.TextInput(
            label='目標 X 座標 (0-9)',
            placeholder='輸入數字 0 到 9',
            required=True,
            max_length=1
        )
        self.y_input = discord.ui.TextInput(
            label='目標 Y 座標 (0-9)',
            placeholder='輸入數字 0 到 9',
            required=True,
            max_length=1
        )
        
        self.add_item(self.card_input)
        self.add_item(self.x_input)
        self.add_item(self.y_input)

    async def on_submit(self, interaction: discord.Interaction):
        card = self.card_input.value
        if card not in self.player.cards:
            await interaction.response.send_message(f"你手牌裡沒有 {card}！可用手牌: {', '.join(self.player.cards)}", ephemeral=True)
            return
            
        try:
            tx = int(self.x_input.value)
            ty = int(self.y_input.value)
            if tx < 0 or tx > 9 or ty < 0 or ty > 9:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("座標必須是 0 到 9 之間的數字！", ephemeral=True)
            return

        self.parent_view.engine.set_action(self.player, card, tx, ty)
        
        player_name = "玩家1" if self.player == self.parent_view.engine.p1 else "玩家2"
        if self.parent_view.engine.p1.user == self.parent_view.engine.p2.user:
             await interaction.response.send_message(f"[{player_name}] 行動已鎖定：{card} 至 ({tx}, {ty})", ephemeral=True)
        else:
             await interaction.response.send_message(f"行動已鎖定：{card} 至 ({tx}, {ty})，等待對手...", ephemeral=True)
             
        await self.parent_view.check_turn_ready()


class BGSView(discord.ui.View):
    def __init__(self, engine: BGSGameEngine):
        super().__init__(timeout=None)
        self.engine = engine
        self.message = None

    @discord.ui.button(label="P1 決定行動", style=discord.ButtonStyle.primary, custom_id="bgs_action_p1")
    async def p1_action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.engine.p1.user:
            await interaction.response.send_message("你不是 P1！", ephemeral=True)
            return
        if self.engine.p1.action_submitted:
            await interaction.response.send_message("你已經決定過行動了！", ephemeral=True)
            return
        await interaction.response.send_modal(ActionModal(self.engine.p1, self, "P1 "))

    @discord.ui.button(label="P2 決定行動", style=discord.ButtonStyle.danger, custom_id="bgs_action_p2")
    async def p2_action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.engine.p2.user:
            await interaction.response.send_message("你不是 P2！", ephemeral=True)
            return
        if self.engine.p2.action_submitted:
            await interaction.response.send_message("你已經決定過行動了！", ephemeral=True)
            return
        await interaction.response.send_modal(ActionModal(self.engine.p2, self, "P2 "))

    async def check_turn_ready(self):
        if self.engine.p1.action_submitted and self.engine.p2.action_submitted:
            res = self.engine.resolve_turn()
            
            p1_name = self.engine.p1.user.display_name if self.engine.p1.user != self.engine.p2.user else "玩家1"
            p2_name = self.engine.p2.user.display_name if self.engine.p1.user != self.engine.p2.user else "玩家2"
            
            log_text = "\n".join(res["log"])
            board_status = f"\n\n📊 **當前狀態**\n[{p1_name}] HP: {self.engine.p1.hp} | 位置: ({self.engine.p1.x}, {self.engine.p1.y}) | 手牌: {', '.join(self.engine.p1.cards)}\n[{p2_name}] HP: {self.engine.p2.hp} | 位置: ({self.engine.p2.x}, {self.engine.p2.y}) | 手牌: {', '.join(self.engine.p2.cards)}"
            
            if res["status"] == "over":
                for child in self.children:
                    child.disabled = True
                await self.message.edit(content=log_text + board_status, view=self)
            else:
                await self.message.edit(content=log_text + board_status, view=self)


class BladeGunShieldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 改用 @app_commands.command 註冊斜線指令
    @app_commands.command(name="bgs", description="發起一場刀槍盾對決！ (可選自己進行測試)")
    async def start_bgs(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("機器人不會玩啦，找個活人或選自己測試！", ephemeral=True)
            return
        
        p1 = Player(interaction.user, 0, 0)
        p2 = Player(opponent, 9, 9)
        engine = BGSGameEngine(p1, p2)
        view = BGSView(engine)
        
        p1_name = p1.user.mention if p1.user != p2.user else "玩家1 (你)"
        p2_name = p2.user.mention if p1.user != p2.user else "玩家2 (也是你)"
        
        msg = f"⚔️ **《刀槍盾》生死鬥開始！** ⚔️\n{p1_name} (位置: 0,0) VS {p2_name} (位置: 9,9)\n雙方滿血 10 點。請點擊下方按鈕盲出你的牌與目標座標！"
        
        # 第一次回應指令，並取得發送出去的訊息物件，存進 view 裡面以便後續更新
        await interaction.response.send_message(msg, view=view)
        view.message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))