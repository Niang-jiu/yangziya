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
        self.items = []
        
        self.queued_items = [] # [新增] 紀錄這回合準備使用的道具 (冰/火)
        self.is_frozen = False # 冰凍狀態
        
        self.selected_card = None
        self.target_x = x
        self.target_y = y
        
        self.is_shielded = False
        self.has_reflected = False  # 紀錄這回合是否有成功反傷
        self.facing = None 
        self.action_submitted = False 

class BGSGameEngine:
    def __init__(self, player1: Player, player2: Player):
        self.board_size = 10
        self.p1 = player1
        self.p2 = player2
        self.turn_count = 1
        self.items_on_board = {} # 記錄地圖上的道具 {(x, y): "道具名"}
        self.turns_since_last_item = 0
        self.fire_zones = {} # 記錄燃燒地形 {(x, y): 剩餘回合}

    def get_relative_target(self, card: str, current_x: int, current_y: int, direction: int, distance: int = 1):
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
        target = self.get_relative_target(card, player.x, player.y, direction, distance)
        
        if not target:
            return False, "方向輸入錯誤！"
            
        tx, ty = target
        # 注意：毒圈不影響邊界，實體的牆壁依然是原本的 board_size
        if tx < 0 or tx >= self.board_size or ty < 0 or ty >= self.board_size:
            return False, "超出邊界ㄌ！"

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

    def force_random_action(self, player: Player):
        while True:
            card = random.choice(player.cards)
            if card in ["刀", "盾"]:
                direction = random.randint(1, 8)
                distance = 1
            else:
                direction = random.randint(1, 4)
                distance = random.randint(1, 9)
                
            is_valid, _ = self.validate_and_set_action(player, card, direction, distance)
            if is_valid:
                break

    def render_board(self):
        # 1. 根據回合數計算目前的縮圈等級 (0, 1, 2...)
        shrink_level = (self.turn_count - 1) // 20
        min_bound = shrink_level
        max_bound = self.board_size - 1 - shrink_level

        # 道具對應圖示
        item_emojis = {"暗黑穿越": "✴️", "燃燒彈": "🧨", "冰凍術": "🧊", "傷害加倍球": "🔴", "回血心": "♥️"}
        
        # 2. 建立地圖陣列
        board = []
        for y in range(self.board_size):
            row = []
            for x in range(self.board_size):
                # 判斷毒圈
                if x < min_bound or x > max_bound or y < min_bound or y > max_bound:
                    row.append("🟩") 
                # 判斷道具
                elif hasattr(self, 'items_on_board') and (x, y) in self.items_on_board:
                    row.append(item_emojis[self.items_on_board[(x, y)]])
                # 判斷燃燒地形
                elif hasattr(self, 'fire_zones') and (x, y) in self.fire_zones:
                    row.append("🔥")
                # 安全區空白格
                else:
                    row.append("🔲")
            board.append(row)
            
        # 3. 標記玩家位置
        if self.p1.x == self.p2.x and self.p1.y == self.p2.y:
            board[self.p1.y][self.p1.x] = "🩸"
        else:
            board[self.p1.y][self.p1.x] = "🐶"
            board[self.p2.y][self.p2.x] = "🐱"
            
        # 4. 加上完美的 X 軸與 Y 軸 (0-9 數字)
        row_icons = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        top_header = "⬛" + "".join(row_icons) 
        
        display = top_header + "\n"
        for idx, row in enumerate(board):
            display += row_icons[idx] + "".join(row) + "\n"
            
        return display

    def resolve_turn(self):
        log = [f"**【第 {self.turn_count} 回合結算】**"]
        
        # 縮圈警告：每 20 回合的下一回合觸發
        if self.turn_count % 20 == 1 and self.turn_count > 1:
            log.append(" **安全區縮小！外圍變成了毒圈！** ")
            
        # 0. 處理前置道具 (燃燒彈、冰凍術) - 在任何移動前生效
        for p in [self.p1, self.p2]:
            for item_name, tx, ty in p.queued_items:
                if item_name == "燃燒彈":
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            fx, fy = tx + dx, ty + dy
                            if 0 <= fx < self.board_size and 0 <= fy < self.board_size:
                                self.fire_zones[(fx, fy)] = 3
                    log.append(f"🔥 **{p.user.display_name} 丟出ㄌ燃燒彈！座標 ({tx}, {ty}) 周圍燒ㄌ起來！**")
                elif item_name == "冰凍術":
                    enemy = self.p2 if p == self.p1 else self.p1
                    if enemy.x == tx and enemy.y == ty:
                        enemy.is_frozen = True
                        log.append(f"🧊 **{p.user.display_name} 命中目標！{enemy.user.display_name} 被冰封，下回合將無法行動！**")
                    else:
                        log.append(f"🧊 **{p.user.display_name} 的冰凍術冰ㄌ空氣 ({tx}, {ty})，恐怖如ㄙ！**")
            p.queued_items.clear()
        
        p1_t = (self.p1.target_x, self.p1.target_y)
        p2_t = (self.p2.target_x, self.p2.target_y)

        # 1. 衝突判定 (含暗黑穿越)
        if p1_t == p2_t:
            log.append("🩸 **雙方站在同一格，開始近距離廝殺！卡牌效果全部失效！**")
            self.p1.x, self.p1.y = p1_t
            self.p2.x, self.p2.y = p2_t
            return self._resolve_clash(log)

        # 2. 刀、盾、暗黑穿越 移動
        for p in [self.p1, self.p2]:
            if p.selected_card in ["刀", "盾", "暗黑穿越"]:
                p.x, p.y = p.target_x, p.target_y
                name_display = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                if p.selected_card == "盾":
                    p.is_shielded = True
                    log.append(f"🛡️ {name_display} 舉起盾牌，移動至 ({p.x}, {p.y})")
                elif p.selected_card == "暗黑穿越":
                    log.append(f" **{name_display} 悄悄瞬移到 ({p.x}, {p.y})！**")
                else:
                    log.append(f"🗡️ {name_display} 拔刀跳躍，移動至 ({p.x}, {p.y})")

        # 3. 槍移動與對衝
        self._resolve_gun_movement(log)

        # 4. 檢查拾取 (球與心瞬間消耗，其他進背包)
        for p in [self.p1, self.p2]:
            if (p.x, p.y) in self.items_on_board:
                item = self.items_on_board.pop((p.x, p.y))
                if item == "回血心":
                    p.hp = min(10, p.hp + 3)
                    log.append(f"♥️ **{p.user.display_name} 吃ㄌ回血心，生命恢復到 {p.hp}！**")
                elif item == "傷害加倍球":
                    p.has_damage_buff = True
                    log.append(f"🔴 **{p.user.display_name} 吃ㄌ加倍球，本次攻擊傷害翻倍！**")
                else:
                    if len(p.items) < 3:
                        p.items.append(item)
                        log.append(f" **{p.user.display_name} 撿ㄌ {item}！**")
                    else:
                        log.append(f" **{p.user.display_name} 包包滿ㄌ {item}！**")

        # 5. 攻擊與反彈
        self._resolve_attacks(log)

        return self._end_turn(log)

    def _resolve_clash(self, log: list):
        p1_dmg = 10 if self.p1.has_damage_buff else 5
        p2_dmg = 10 if self.p2.has_damage_buff else 5
        
        self.p1.hp -= p2_dmg
        self.p2.hp -= p1_dmg
        
        log.append(f"🩸 廝殺結果：雙方受到嚴重傷害！")
        return self._end_turn(log)

    def _resolve_gun_movement(self, log: list):
        p1_gun = self.p1.selected_card == "槍"
        p2_gun = self.p2.selected_card == "槍"

        if p1_gun and p2_gun and self._is_path_crossing():
            log.append("💥 **雙方持槍對衝！互相穿透並造成 4 點傷害！**")
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
                        p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                        log.append(f" {p_name} 衝刺撞到對手，停在ㄌ ({p.x}, {p.y})")
                        break
                
                if not hit:
                    p.x, p.y = p.target_x, p.target_y
                    p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
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
        # 階段 1：處理刀、槍、暗黑的攻擊判定（包含盾的反傷）
        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            dmg = 0
            if p.selected_card == "刀":
                in_range = False
                if p.facing == "UP" and p.y - 3 <= enemy.y <= p.y and abs(enemy.x - p.x) <= 1: in_range = True
                elif p.facing == "DOWN" and p.y <= enemy.y <= p.y + 3 and abs(enemy.x - p.x) <= 1: in_range = True
                elif p.facing == "LEFT" and p.x - 3 <= enemy.x <= p.x and abs(enemy.y - p.y) <= 1: in_range = True
                elif p.facing == "RIGHT" and p.x <= enemy.x <= p.x + 3 and abs(enemy.y - p.y) <= 1: in_range = True
                
                if enemy.x == p.x and enemy.y == p.y:
                    in_range = False
                if in_range: dmg = 2
                    
            elif p.selected_card == "槍":
                dist = abs(enemy.x - p.x) + abs(enemy.y - p.y)
                if (enemy.x == p.x or enemy.y == p.y) and dist == 1:
                    dmg = 4
                    
            elif p.selected_card == "暗黑穿越":
                if abs(enemy.x - p.x) <= 1 and abs(enemy.y - p.y) <= 1:
                    dmg = 2

            # 套用傷害加倍球的邏輯
            if p.has_damage_buff and dmg > 0:
                dmg *= 2

            if dmg > 0:
                p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                e_name = "🐶 " + enemy.user.display_name if enemy == self.p1 else "🐱 " + enemy.user.display_name
                
                if enemy.is_shielded:
                    reflect = int(dmg * 0.5)
                    p.hp -= reflect
                    if reflect > 0: 
                        enemy.has_reflected = True
                    log.append(f"🛡️ {e_name} 的盾牌反彈ㄌ攻擊！ {p_name} 受到 {reflect} 點反傷！")
                else:
                    enemy.hp -= dmg
                    action_text = "偷襲" if p.selected_card == "暗黑穿越" else "命中ㄌ"
                    log.append(f"⚔️ {p_name} {action_text}！ 對 {e_name} 造成 {dmg} 點傷害！")

        # 階段 2：檢查是否有未觸發反傷的盾牌，釋放衝擊波
        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            if p.selected_card == "盾" and not getattr(p, 'has_reflected', False):
                if abs(enemy.x - p.x) <= 1 and abs(enemy.y - p.y) <= 1:
                    if not (enemy.x == p.x and enemy.y == p.y):
                        enemy.hp -= 1
                        p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                        e_name = "🐶 " + enemy.user.display_name if enemy == self.p1 else "🐱 " + enemy.user.display_name
                        log.append(f" {p_name} 的盾牌未受攻擊，釋放了能量波！對周圍的 {e_name} 造成 1 點傷害！")

    def _end_turn(self, log: list):
        # 結算地形與毒圈傷害
        shrink_level = (self.turn_count - 1) // 20
        min_bound = shrink_level
        max_bound = self.board_size - 1 - shrink_level
        
        for p in [self.p1, self.p2]:
            if (p.x, p.y) in self.fire_zones:
                p.hp -= 2
                log.append(f"🔥 **{p.user.display_name} 踩在燃燒地形，受到 2 點燃燒傷害！**")
                
            if shrink_level > 0:
                if p.x < min_bound or p.x > max_bound or p.y < min_bound or p.y > max_bound:
                    p.hp -= 1
                    log.append(f" {p.user.display_name} 喜歡毒，受到 1 點毒氣傷害！")

        # 判定生死
        if self.p1.hp <= 0 and self.p2.hp <= 0:
            log.append("\n **雙方同時倒下，遊戲平手！**")
            return {"status": "over", "log": log}
        elif self.p1.hp <= 0:
            log.append(f"\n **{self.p2.user.mention} 獲得勝利！**")
            return {"status": "over", "log": log}
        elif self.p2.hp <= 0:
            log.append(f"\n **{self.p1.user.mention} 獲得勝利！**")
            return {"status": "over", "log": log}
        
        # 道具生成邏輯
        self.turns_since_last_item += 1
        if random.random() < 0.05 or self.turns_since_last_item >= 10:
            available_spots = [(x, y) for x in range(self.board_size) for y in range(self.board_size) 
                               if (x, y) not in [(self.p1.x, self.p1.y), (self.p2.x, self.p2.y)] and (x, y) not in self.items_on_board]
            if available_spots:
                pos = random.choice(available_spots)
                new_item = random.choice(["暗黑穿越", "燃燒彈", "冰凍術", "傷害加倍球", "回血心"])
                self.items_on_board[pos] = new_item
                self.turns_since_last_item = 0
                log.append(f"**地圖上出現ㄌ {new_item}！**")

        # 燃燒地形衰減
        self.fire_zones = {pos: t - 1 for pos, t in self.fire_zones.items() if t > 1}
        
        # 處理冰凍狀態並重置
        self.p1.action_submitted = False
        self.p2.action_submitted = False
        
        for p in [self.p1, self.p2]:
            if getattr(p, 'is_frozen', False):
                p.action_submitted = True
                p.selected_card = "被冰封"
                p.target_x, p.target_y = p.x, p.y
                p.is_frozen = False
            else:
                if p.selected_card in p.cards:
                    p.cards.remove(p.selected_card)
                    p.cards.append(random.choice(["刀", "槍", "盾"]))
                
            p.is_shielded = False
            p.has_reflected = False
            p.has_damage_buff = False
        
        self.turn_count += 1
        return {"status": "continue", "log": log}


# --- Discord UI 介面 ---

class GridBladeButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🗡️", style=discord.ButtonStyle.secondary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        
        if view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
            
        if interaction.user != view.player.user:
            return await interaction.response.send_message("這不是你的面板！", ephemeral=True)
            
        if view.player.action_submitted:
            return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)
            
        if "刀" not in view.player.cards:
            return await interaction.response.send_message("你手牌裡沒有【刀】！請換一個。", ephemeral=True)

        is_valid, msg = view.main_view.engine.validate_and_set_action(view.player, "刀", self.direction)
        if not is_valid:
            return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

        await interaction.response.edit_message(content=f"✅ 第 {view.main_view.engine.turn_count} 回合行動已鎖定：【刀】！\n請等待結算...", view=view)
        await view.main_view.check_both_submitted()

class GridShieldButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🛡️", style=discord.ButtonStyle.success, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        
        if view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
            
        if interaction.user != view.player.user:
            return await interaction.response.send_message("這不是你的面板!", ephemeral=True)
            
        if view.player.action_submitted:
            return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)

        if "盾" not in view.player.cards:
            return await interaction.response.send_message("你手牌裡沒有【盾】！請換一個。", ephemeral=True)

        is_valid, msg = view.main_view.engine.validate_and_set_action(view.player, "盾", self.direction)
        if not is_valid:
            return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

        await interaction.response.edit_message(content=f"✅ 第 {view.main_view.engine.turn_count} 回合行動已鎖定：【盾】！\n請等待結算...", view=view)
        await view.main_view.check_both_submitted()

class GridSpearButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="📌", style=discord.ButtonStyle.primary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        
        if view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
            
        if interaction.user != view.player.user:
            return await interaction.response.send_message("這不是你的面板！", ephemeral=True)
            
        if view.player.action_submitted:
            return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)

        if "槍" not in view.player.cards:
            return await interaction.response.send_message("你手牌裡沒有【槍】！請換一個。", ephemeral=True)

        await interaction.response.send_modal(GunDistanceModal(view.player, self.direction, view.main_view, view, view.main_view.engine.turn_count))

class GunDistanceModal(discord.ui.Modal):
    dist_input = discord.ui.TextInput(
        label='衝刺距離 (1-9)', placeholder='輸入 1~9', required=True, max_length=1
    )

    def __init__(self, player, direction, main_view, control_view, turn_count):
        dir_names = {1: "向下", 2: "向右", 3: "向左", 4: "向上"}
        super().__init__(title=f'設定槍的衝刺距離 ({dir_names[direction]})')
        self.player = player
        self.direction = direction
        self.main_view = main_view
        self.control_view = control_view
        self.turn_count = turn_count

    async def on_submit(self, interaction: discord.Interaction):
        if self.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
            
        if self.player.action_submitted or self.main_view.engine.turn_count != self.turn_count:
            return await interaction.response.send_message("回合已過或已出招！", ephemeral=True)

        try:
            dist = int(self.dist_input.value)
            if dist < 1 or dist > 9:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("輸入格式錯誤！距離需為 1~9。", ephemeral=True)

        is_valid, msg = self.main_view.engine.validate_and_set_action(self.player, "槍", self.direction, dist)
        if not is_valid:
            return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

        await interaction.response.edit_message(content=f"✅ 第 {self.turn_count} 回合行動已鎖定：【槍】(距離 {dist})！\n請等待結算...", view=self.control_view)
        await self.main_view.check_both_submitted()

class GridEmptyButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=row, disabled=True)

class GridCenterButton(discord.ui.Button):
    def __init__(self, row, player: Player, engine: BGSGameEngine):
        emoji = "🐶" if player == engine.p1 else "🐱"
        super().__init__(label="\u200b", emoji=emoji, style=discord.ButtonStyle.secondary, row=row, disabled=True)

class GridSurrenderButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="\u200b", emoji="🏳️", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        
        if view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束了!", ephemeral=True)
            
        if interaction.user != view.player.user:
            return await interaction.response.send_message("這不是你的面板！", ephemeral=True)

        view.main_view.game_over = True
        if view.main_view.timer_task:
            view.main_view.timer_task.cancel()

        loser = interaction.user
        winner = view.main_view.engine.p2 if loser == view.main_view.engine.p1.user else view.main_view.engine.p1

        view.main_view.last_log = [f"🏳️ **{loser.mention} 投降！**\n **{winner.user.mention} 獲得勝利！**"]
        
        await interaction.response.edit_message(content="你輸ㄌ。", view=view)
        await view.main_view.safe_edit_main_message()


class ItemUseButton(discord.ui.Button):
    def __init__(self, item_name, index):
        emojis = {"暗黑穿越": "✴️", "燃燒彈": "🧨", "冰凍術": "🧊", "傷害加倍球": "🔴", "回血心": "♥️"}
        super().__init__(emoji=emojis.get(item_name), style=discord.ButtonStyle.success)
        self.item_name = item_name
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        p = view.player
        
        if view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ！", ephemeral=True)
        if interaction.user != p.user:
            return await interaction.response.send_message("這不是你的道具！", ephemeral=True)

        # 冰、火、暗黑需要座標，彈出 Modal 讓玩家輸入
        if self.item_name in ["燃燒彈", "冰凍術", "暗黑穿越"]:
            await interaction.response.send_modal(TargetingModal(p, self.item_name, self.index, view))


class TargetingModal(discord.ui.Modal):
    coord_input = discord.ui.TextInput(
        label='目標座標 (先輸入橫的 X，再直的 Y)', 
        placeholder='例如 34 代表橫的 3，直的 4', 
        min_length=2, max_length=2, required=True
    )

    def __init__(self, player, item_name, index, control_view):
        super().__init__(title=f'使用道具：{item_name}')
        self.player = player
        self.item_name = item_name
        self.index = index
        self.control_view = control_view

    async def on_submit(self, interaction: discord.Interaction):
        if self.control_view.main_view.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ！", ephemeral=True)

        raw_val = self.coord_input.value
        
        try:
            target_x = int(raw_val[0])
            target_y = int(raw_val[1])
            if not (0 <= target_x < 10 and 0 <= target_y < 10):
                raise ValueError
        except:
            return await interaction.response.send_message("座標格式錯誤！請輸入兩位數字(00-99)。", ephemeral=True)

        if self.item_name in ["燃燒彈", "冰凍術"]:
            # 加入列隊等待回合結算優先處理
            self.player.queued_items.append((self.item_name, target_x, target_y))
            self.player.items.pop(self.index)
            await interaction.response.edit_message(content=f"✅ 已準備 {self.item_name}！請繼續選擇你的出牌（刀/槍/盾/暗黑）。", view=ControlPanel(self.control_view.main_view, self.player))

        elif self.item_name == "暗黑穿越":
            if self.player.action_submitted:
                return await interaction.response.send_message("你這回合已經出過招了，無法再使用暗黑穿越！", ephemeral=True)
            
            # 作為主卡牌行動
            self.player.selected_card = "暗黑穿越"
            self.player.target_x = target_x
            self.player.target_y = target_y
            self.player.action_submitted = True
            self.player.items.pop(self.index)
            
            await self.control_view.main_view.safe_edit_main_message()
            await interaction.response.edit_message(content=f"✅ 行動已鎖定：【暗黑穿越】！\n請等待結算...", view=ControlPanel(self.control_view.main_view, self.player))
            await self.control_view.main_view.check_both_submitted()


# --- 隱藏操控面板 ---
class ControlPanel(discord.ui.View):
    def __init__(self, main_view, player):
        super().__init__(timeout=None)
        self.main_view = main_view
        self.player = player
        
        # --- 動態準備 3 個道具格 ---
        item_buttons = []
        for i in range(3):
            if i < len(self.player.items):
                item_buttons.append(ItemUseButton(self.player.items[i], index=i))
            else:
                item_buttons.append(None) 

        def add_placeholder(index, row):
            btn = item_buttons[index]
            if btn:
                btn.row = row
                self.add_item(btn)
            else:
                self.add_item(GridEmptyButton(row))

        # --- Row 0 ---
        add_placeholder(0, 0)
        self.add_item(GridBladeButton(8, 0))
        self.add_item(GridSpearButton(4, 0)) 
        self.add_item(GridBladeButton(1, 0))
        add_placeholder(1, 0)

        # --- Row 1 ---
        self.add_item(GridBladeButton(7, 1))
        self.add_item(GridShieldButton(7, 1))
        self.add_item(GridShieldButton(8, 1))
        self.add_item(GridShieldButton(1, 1))
        self.add_item(GridBladeButton(2, 1))

        # --- Row 2 ---
        self.add_item(GridSpearButton(3, 2)) 
        self.add_item(GridShieldButton(6, 2))
        self.add_item(GridCenterButton(2, self.player, self.main_view.engine))
        self.add_item(GridShieldButton(2, 2))
        self.add_item(GridSpearButton(2, 2)) 

        # --- Row 3 ---
        self.add_item(GridBladeButton(6, 3))
        self.add_item(GridShieldButton(5, 3))
        self.add_item(GridShieldButton(4, 3))
        self.add_item(GridShieldButton(3, 3))
        self.add_item(GridBladeButton(3, 3))

        # --- Row 4 ---
        add_placeholder(2, 4)
        self.add_item(GridBladeButton(5, 4))
        self.add_item(GridSpearButton(1, 4)) 
        self.add_item(GridBladeButton(4, 4))
        self.add_item(GridSurrenderButton(4))


# --- 主公開面板 ---
class BGSMainView(discord.ui.View):
    def __init__(self, engine: BGSGameEngine):
        super().__init__(timeout=None)
        self.engine = engine
        self.message = None
        self.timer_task = None
        self.game_over = False
        self.last_log = ["⚔️ **《刀槍盾》對戰開始！** ⚔️\n(猜測敵人的行動並攻擊！)"]

    def get_message_content(self):
        board_display = self.engine.render_board()
        p1_mention = self.engine.p1.user.mention
        p2_mention = self.engine.p2.user.mention

        status_text = (
            f"\n{board_display}\n"
            f"🐶 {p1_mention} HP: {self.engine.p1.hp} | 座標: ({self.engine.p1.x}, {self.engine.p1.y}) | 手牌: {', '.join(self.engine.p1.cards)}\n"
            f"🐱 {p2_mention} HP: {self.engine.p2.hp} | 座標: ({self.engine.p2.x}, {self.engine.p2.y}) | 手牌: {', '.join(self.engine.p2.cards)}"
        )

        full_text = "\n".join(self.last_log) + "\n" + status_text

        if not self.game_over:
            unsubmitted = []
            if not self.engine.p1.action_submitted: unsubmitted.append("🐶")
            if not self.engine.p2.action_submitted: unsubmitted.append("🐱")
            
            if unsubmitted:
                full_text += f"\n\n⏳ **等待出招中：{' '.join(unsubmitted)}**"
            full_text += "\n\n(點擊按鈕召喚遊戲面板，並在面板上出招！)"

        return full_text

    async def safe_edit_main_message(self):
        if not self.message:
            return

        content = self.get_message_content()
        try:
            await self.message.edit(content=content, view=self)
        except discord.HTTPException as e:
            if e.code == 50027 or e.status in (401, 404): 
                try:
                    channel = self.message.channel
                    new_msg = await channel.fetch_message(self.message.id)
                    await new_msg.edit(content=content, view=self)
                    self.message = new_msg  
                except Exception as fetch_e:
                    print(f"[BGS] 續命失敗: {fetch_e}")
            else:
                print(f"[BGS] 未知的編輯錯誤: {e}")
        except Exception as e:
            print(f"[BGS] 發生錯誤: {e}")

    @discord.ui.button(label="🐶 喚出狗玩家面板", style=discord.ButtonStyle.secondary)
    async def spawn_dog_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ", ephemeral=True)
            
        if interaction.user != self.engine.p1.user:
            return await interaction.response.send_message("不要搶別人ㄉ啦！", ephemeral=True)
        panel = ControlPanel(self, self.engine.p1)
        await interaction.response.send_message(
            "🎮 **這是你ㄉ遊戲面板**\n請直接在這裡點擊出招！", 
            view=panel, 
            ephemeral=True
        )

    @discord.ui.button(label="🐱 喚出貓玩家面板", style=discord.ButtonStyle.secondary)
    async def spawn_cat_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            return await interaction.response.send_message("遊戲結束ㄌ", ephemeral=True)
            
        if interaction.user != self.engine.p2.user:
            return await interaction.response.send_message("不要搶別人ㄉ啦！", ephemeral=True)
        panel = ControlPanel(self, self.engine.p2)
        await interaction.response.send_message(
            "🎮 **這是你ㄉ遊戲面板**\n請直接在這裡點擊出招！", 
            view=panel, 
            ephemeral=True
        )

    async def start_timer(self):
        turn_now = self.engine.turn_count
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return 
            
        if not self.game_over and self.engine.turn_count == turn_now:
            timeout_msgs = []
            if not self.engine.p1.action_submitted:
                self.engine.force_random_action(self.engine.p1)
                timeout_msgs.append(f"⏳ **{self.engine.p1.user.display_name} 想太久ㄌ！隨便亂走**")
            if not self.engine.p2.action_submitted:
                self.engine.force_random_action(self.engine.p2)
                timeout_msgs.append(f"⏳ **{self.engine.p2.user.display_name} 想太久ㄌ！隨便亂走**")
            
            await self.check_both_submitted(timeout_msgs)

    async def check_both_submitted(self, timeout_msgs=None):
        if self.engine.p1.action_submitted and self.engine.p2.action_submitted:
            res = self.engine.resolve_turn()
            self.last_log = res["log"]
            if timeout_msgs:
                self.last_log = timeout_msgs + self.last_log
            if res["status"] == "over":
                self.game_over = True
            
            await self.safe_edit_main_message()
            
            if self.timer_task:
                self.timer_task.cancel()
            if not self.game_over:
                self.timer_task = asyncio.create_task(self.start_timer())
        else:
            actor = self.engine.p1 if self.engine.p1.action_submitted else self.engine.p2
            if timeout_msgs:
                 self.last_log = timeout_msgs + [f"✅ **{actor.user.display_name}** 已鎖定行動，等待對手..."]
            else:
                 self.last_log = [f"✅ **{actor.user.display_name}** 已鎖定行動，等待對手..."]
                 
            await self.safe_edit_main_message()


class BladeGunShieldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bgs", description="發起一場刀槍盾對決！")
    async def start_bgs(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("對不起鴨，我不會玩", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        p1 = Player(interaction.user, 0, 0)
        p2 = Player(opponent, 9, 9)
        engine = BGSGameEngine(p1, p2)
        view = BGSMainView(engine)
        
        await interaction.followup.send(view.get_message_content(), view=view)
        view.message = await interaction.original_response()
        
        view.timer_task = asyncio.create_task(view.start_timer())

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))