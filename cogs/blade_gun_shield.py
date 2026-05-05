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
        self.items = [] # 只會存放 暗黑穿越、燃燒彈、冰凍術
        
        self.queued_items = [] 
        self.is_frozen = False 
        self.burn_turns = 0    
        
        self.selected_card = None
        self.target_x = x
        self.target_y = y
        
        # 記錄每次行動的向量，用來判定面向與盾牌擊退方向
        self.move_dx = 0
        self.move_dy = 0
        
        self.is_shielded = False
        self.has_reflected = False
        self.facing = None 
        self.action_submitted = False
        self.gun_hit_enemy = False

class BGSGameEngine:
    def __init__(self, player1: Player, player2: Player):
        self.board_size = 10
        self.p1 = player1
        self.p2 = player2
        self.turn_count = 1
        self.items_on_board = {} 
        self.turns_since_last_item = 0
        self.fire_zones = {} 

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
        if tx < 0 or tx >= self.board_size or ty < 0 or ty >= self.board_size:
            return False, "超出邊界ㄌ！"

        player.selected_card = card
        player.target_x = tx
        player.target_y = ty
        player.action_submitted = True
        
        dx = player.target_x - player.x
        dy = player.target_y - player.y
        
        # 記錄移動向量與判定面向
        player.move_dx = dx
        player.move_dy = dy
        
        if abs(dy) > abs(dx):
            player.facing = "UP" if dy < 0 else "DOWN"
        elif abs(dx) > abs(dy):
            player.facing = "LEFT" if dx < 0 else "RIGHT"
        elif dx != 0:
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
                distance = random.randint(1, 4)
                
            is_valid, _ = self.validate_and_set_action(player, card, direction, distance)
            if is_valid:
                break

    def render_board(self):
        shrink_level = self.turn_count // 8
        min_bound = shrink_level
        max_bound = self.board_size - 1 - shrink_level

        item_emojis = {"暗黑穿越": "✴️", "燃燒彈": "🧨", "冰凍術": "🧊", "傷害加倍球": "🔴", "回血心": "♥️"}
        
        board = []
        for y in range(self.board_size):
            row = []
            for x in range(self.board_size):
                if (x, y) in self.items_on_board:
                    row.append(item_emojis[self.items_on_board[(x, y)]])
                elif x < min_bound or x > max_bound or y < min_bound or y > max_bound:
                    row.append("🟩") 
                elif (x, y) in self.fire_zones:
                    row.append("🔥")
                else:
                    row.append("🔲")
            board.append(row)
            
        if self.p1.x == self.p2.x and self.p1.y == self.p2.y:
            board[self.p1.y][self.p1.x] = "🩸"
        else:
            board[self.p1.y][self.p1.x] = "🐶"
            board[self.p2.y][self.p2.x] = "🐱"
            
        row_icons = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        top_header = "⬛" + "".join(row_icons) 
        
        display = top_header + "\n"
        for idx, row in enumerate(board):
            display += row_icons[idx] + "".join(row) + "\n"
            
        return display

    def resolve_turn(self):
        log = [f"**【第 {self.turn_count} 回合結算】**"]
        
        if self.turn_count % 8 == 0 and self.turn_count > 0:
            log.append("☠️ **毒氣即將在下回合擴散，安全區縮小！**")
            
        for p in [self.p1, self.p2]:
            for item_name, tx, ty in p.queued_items:
                if item_name == "燃燒彈":
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            fx, fy = tx + dx, ty + dy
                            if 0 <= fx < self.board_size and 0 <= fy < self.board_size:
                                self.fire_zones[(fx, fy)] = 1
                    log.append(f"🔥 **{p.user.display_name} 丟出了燃燒彈！座標 ({tx}, {ty}) 周圍燒了起來！**")
                elif item_name == "冰凍術":
                    enemy = self.p2 if p == self.p1 else self.p1
                    if abs(enemy.target_x - tx) <= 1 and abs(enemy.target_y - ty) <= 1:
                        enemy.is_frozen = True
                        enemy.selected_card = "被冰封"
                        enemy.target_x, enemy.target_y = enemy.x, enemy.y
                        log.append(f"🧊 **{p.user.display_name} 成功預判！冰凍術命中目標！{enemy.user.display_name} 本回合無法行動！**")
                    else:
                        log.append(f"🧊 **{p.user.display_name} 的冰凍術砸空了！**")
            p.queued_items.clear()
        
        p1_t = (self.p1.target_x, self.p1.target_y)
        p2_t = (self.p2.target_x, self.p2.target_y)

        # 1. 衝突判定
        if p1_t == p2_t:
            self.p1.x, self.p1.y = p1_t
            self.p2.x, self.p2.y = p2_t
            return self._resolve_clash(log)

        # 2. 刀、盾、暗黑穿越移動
        for p in [self.p1, self.p2]:
            if p.selected_card in ["刀", "盾", "暗黑穿越"]:
                p.x, p.y = p.target_x, p.target_y
                name_display = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                if p.selected_card == "盾":
                    p.is_shielded = True
                    log.append(f"🛡️ {name_display} 舉起盾牌，移動至 ({p.x}, {p.y})")
                elif p.selected_card == "暗黑穿越":
                    log.append(f"✴️ **{name_display} 使用暗黑穿越，瞬移到 ({p.x}, {p.y})！**")
                elif p.selected_card == "刀":
                    log.append(f"🗡️ {name_display} 拔刀跳躍，移動至 ({p.x}, {p.y})")

        # 3. 槍移動與對衝
        self._resolve_gun_movement(log)

        # 4. 檢查拾取
        for p in [self.p1, self.p2]:
            if (p.x, p.y) in self.items_on_board:
                item = self.items_on_board.pop((p.x, p.y))
                if item == "回血心":
                    p.hp = min(10, p.hp + 3)
                    log.append(f"♥️ **{p.user.display_name} 踩到了回血心，生命恢復 3 點！**")
                elif item == "傷害加倍球":
                    p.has_damage_buff = True
                    log.append(f"🔴 **{p.user.display_name} 踩到了加倍球，下次傷害翻倍！**")
                else:
                    p.items.append(item)
                    log.append(f"🎒 **{p.user.display_name} 撿到了 {item}！**")

        # 5. 攻擊與反彈
        self._resolve_attacks(log)

        return self._end_turn(log)

    def _resolve_clash(self, log: list):
        log.append("🩸 **雙方踩入同一格，觸發近距離廝殺！卡牌效果失效！**")
        
        if (self.p1.x, self.p1.y) in self.items_on_board:
            item = self.items_on_board.pop((self.p1.x, self.p1.y))
            if item == "回血心":
                self.p1.hp = min(10, self.p1.hp + 3)
                self.p2.hp = min(10, self.p2.hp + 3)
                log.append(f"♥️ **雙方在廝殺時踩到回血心，生命皆恢復 3 點！**")
            elif item == "傷害加倍球":
                self.p1.has_damage_buff = True
                self.p2.has_damage_buff = True
                log.append(f"🔴 **雙方在廝殺時踩到加倍球，皆獲得傷害加倍！**")
            else:
                self.p1.items.append(item)
                self.p2.items.append(item)
                log.append(f"🎁 **雙方在廝殺時同時撿起了地上的 {item}！**")

        p1_dmg = 2 if self.p1.has_damage_buff else 1
        p2_dmg = 2 if self.p2.has_damage_buff else 1
        
        for i in range(5):
            self.p2.hp -= p1_dmg
            self.p1.hp -= p2_dmg
            if self.p1.hp <= 0 or self.p2.hp <= 0:
                break
                
        if self.p1.has_damage_buff: self.p1.has_damage_buff = False
        if self.p2.has_damage_buff: self.p2.has_damage_buff = False
        
        log.append(f"🩸 經過慘烈的互砍，雙方受到了嚴重傷害！")
        return self._end_turn(log)

    def _resolve_gun_movement(self, log: list):
        p1_gun = self.p1.selected_card == "槍"
        p2_gun = self.p2.selected_card == "槍"

        # 檢查面對面對衝
        is_face_to_face = False
        if p1_gun and p2_gun:
            if self.p1.facing == "UP" and self.p2.facing == "DOWN" and self.p1.x == self.p2.x and self.p1.y > self.p2.y and self.p1.target_y <= self.p2.target_y:
                is_face_to_face = True
            elif self.p1.facing == "DOWN" and self.p2.facing == "UP" and self.p1.x == self.p2.x and self.p1.y < self.p2.y and self.p1.target_y >= self.p2.target_y:
                is_face_to_face = True
            elif self.p1.facing == "LEFT" and self.p2.facing == "RIGHT" and self.p1.y == self.p2.y and self.p1.x > self.p2.x and self.p1.target_x <= self.p2.target_x:
                is_face_to_face = True
            elif self.p1.facing == "RIGHT" and self.p2.facing == "LEFT" and self.p1.y == self.p2.y and self.p1.x < self.p2.x and self.p1.target_x >= self.p2.target_x:
                is_face_to_face = True

        if is_face_to_face:
            log.append("💥 **雙方持槍對衝！互相穿透並受到重創！**")
            p1_dmg = 8 if self.p1.has_damage_buff else 4
            p2_dmg = 8 if self.p2.has_damage_buff else 4
            
            self.p1.hp -= p2_dmg
            self.p2.hp -= p1_dmg
            if p1_dmg > 4: self.p1.has_damage_buff = False
            if p2_dmg > 4: self.p2.has_damage_buff = False
            
            self.p1.x, self.p1.y = self.p1.target_x, self.p1.target_y
            self.p2.x, self.p2.y = self.p2.target_x, self.p2.target_y
            return

        # 若非對衝，則進行逐格模擬，確保只攻擊前方的敵人
        def get_gun_params(p):
            dx = 1 if p.target_x > p.x else (-1 if p.target_x < p.x else 0)
            dy = 1 if p.target_y > p.y else (-1 if p.target_y < p.y else 0)
            dist = max(abs(p.target_x - p.x), abs(p.target_y - p.y))
            return dx, dy, dist
            
        p1_dx, p1_dy, p1_dist = get_gun_params(self.p1) if p1_gun else (0,0,0)
        p2_dx, p2_dy, p2_dist = get_gun_params(self.p2) if p2_gun else (0,0,0)
        
        p1_stopped = not p1_gun
        p2_stopped = not p2_gun
        
        max_dist = max(p1_dist, p2_dist)
        
        for step in range(1, max_dist + 1):
            p1_next_x = self.p1.x + p1_dx if not p1_stopped and step <= p1_dist else self.p1.x
            p1_next_y = self.p1.y + p1_dy if not p1_stopped and step <= p1_dist else self.p1.y
            
            p2_next_x = self.p2.x + p2_dx if not p2_stopped and step <= p2_dist else self.p2.x
            p2_next_y = self.p2.y + p2_dy if not p2_stopped and step <= p2_dist else self.p2.y
            
            p1_hits = False
            p2_hits = False
            
            if not p1_stopped and step <= p1_dist:
                if (p1_next_x == self.p2.x and p1_next_y == self.p2.y) or (p1_next_x == p2_next_x and p1_next_y == p2_next_y):
                    p1_hits = True
            
            if not p2_stopped and step <= p2_dist:
                if (p2_next_x == self.p1.x and p2_next_y == self.p1.y) or (p2_next_x == p1_next_x and p2_next_y == p1_next_y):
                    p2_hits = True
                    
            if p1_hits:
                self.p1.gun_hit_enemy = True
                p1_stopped = True
                p_name = "🐶 " + self.p1.user.display_name
                log.append(f"📌 {p_name} 衝刺撞到對手，停在了 ({self.p1.x}, {self.p1.y})")
                
            if p2_hits:
                self.p2.gun_hit_enemy = True
                p2_stopped = True
                p_name = "🐱 " + self.p2.user.display_name
                log.append(f"📌 {p_name} 衝刺撞到對手，停在了 ({self.p2.x}, {self.p2.y})")
                
            if not p1_stopped and step <= p1_dist and not p1_hits:
                self.p1.x, self.p1.y = p1_next_x, p1_next_y
            if not p2_stopped and step <= p2_dist and not p2_hits:
                self.p2.x, self.p2.y = p2_next_x, p2_next_y

        for p in [self.p1, self.p2]:
            if p.selected_card == "槍" and not getattr(p, 'gun_hit_enemy', False):
                p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                log.append(f"💨 {p_name} 持槍衝刺至 ({p.x}, {p.y})")

    def _resolve_attacks(self, log: list):
        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            dmg = 0
            if p.selected_card == "刀":
                in_range = False
                if p.facing == "UP":
                    if p.y - 3 <= enemy.y <= p.y - 1 and abs(enemy.x - p.x) <= 1: in_range = True
                    elif enemy.y == p.y and abs(enemy.x - p.x) == 1: in_range = True
                elif p.facing == "DOWN":
                    if p.y + 1 <= enemy.y <= p.y + 3 and abs(enemy.x - p.x) <= 1: in_range = True
                    elif enemy.y == p.y and abs(enemy.x - p.x) == 1: in_range = True
                elif p.facing == "LEFT":
                    if p.x - 3 <= enemy.x <= p.x - 1 and abs(enemy.y - p.y) <= 1: in_range = True
                    elif enemy.x == p.x and abs(enemy.y - p.y) == 1: in_range = True
                elif p.facing == "RIGHT":
                    if p.x + 1 <= enemy.x <= p.x + 3 and abs(enemy.y - p.y) <= 1: in_range = True
                    elif enemy.x == p.x and abs(enemy.y - p.y) == 1: in_range = True
                
                if in_range: dmg = 2
                    
            elif p.selected_card == "槍" and getattr(p, 'gun_hit_enemy', False):
                dmg = 4
                    
            elif p.selected_card == "暗黑穿越":
                if abs(enemy.x - p.target_x) <= 2 and abs(enemy.y - p.target_y) <= 2:
                    dmg = 2

            if p.has_damage_buff and dmg > 0:
                dmg *= 2
                p.has_damage_buff = False 

            if dmg > 0:
                p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                e_name = "🐶 " + enemy.user.display_name if enemy == self.p1 else "🐱 " + enemy.user.display_name
                
                if enemy.is_shielded:
                    reflect = int(dmg * 0.5)
                    p.hp -= reflect
                    enemy.has_reflected = True
                    log.append(f"🛡️ {e_name} 的盾牌反彈ㄌ{reflect} 點反傷給 {p_name} !")
                else:
                    enemy.hp -= dmg
                    action_text = "黑暗力量爆發" if p.selected_card == "暗黑穿越" else "命中了"
                    log.append(f"⚔️ {p_name} {action_text}！對 {e_name} 造成 {dmg} 點傷害！")

        # 未受攻擊的盾牌範圍傷害 (含擊退與撞牆判定) - 統一收集後再結算
        shield_hits = []
        for p, enemy in [(self.p1, self.p2), (self.p2, self.p1)]:
            if p.selected_card == "盾" and not getattr(p, 'has_reflected', False):
                if abs(enemy.x - p.x) <= 1 and abs(enemy.y - p.y) <= 1:
                    # 不在同一格才觸發掃蕩
                    if not (enemy.x == p.x and enemy.y == p.y):
                        shield_hits.append((p, enemy))

        for p, enemy in shield_hits:
            sweep_dmg = 2 if p.has_damage_buff else 1
            enemy.hp -= sweep_dmg
            if p.has_damage_buff: p.has_damage_buff = False
            
            # --- 擊退與撞牆邏輯 ---
            kb_dx = p.move_dx
            kb_dy = p.move_dy
            
            # 標準化為單位向量以防萬一
            if kb_dx != 0: kb_dx //= abs(kb_dx)
            if kb_dy != 0: kb_dy //= abs(kb_dy)
            
            hit_wall = False
            actual_push = 0
            # 固定推 3 格
            for step in range(3):
                next_x = enemy.x + kb_dx
                next_y = enemy.y + kb_dy
                if 0 <= next_x < self.board_size and 0 <= next_y < self.board_size:
                    enemy.x = next_x
                    enemy.y = next_y
                    enemy.target_x = next_x
                    enemy.target_y = next_y
                    actual_push += 1
                else:
                    hit_wall = True
                    break # 撞到牆就停下來
            
            wall_msg = ""
            if hit_wall:
                enemy.hp -= 1
                wall_msg = "，並狠狠撞上邊界額外受到 1 點傷害！"
            else:
                wall_msg = "！"
                
            p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
            e_name = "🐶 " + enemy.user.display_name if enemy == self.p1 else "🐱 " + enemy.user.display_name
            log.append(f"💨 {p_name} 的盾牌未受攻擊釋放衝擊波！對 {e_name} 造成 {sweep_dmg} 點傷害，並往移動方向擊退 {actual_push} 格{wall_msg}")

    def _end_turn(self, log: list):
        shrink_level = self.turn_count // 8
        min_bound = shrink_level
        max_bound = self.board_size - 1 - shrink_level
        
        for p in [self.p1, self.p2]:
            if (p.x, p.y) in self.fire_zones:
                if p.burn_turns < 3:
                    p.burn_turns = 3
            
            if p.burn_turns > 0:
                p.hp -= 1
                p.burn_turns -= 1
                log.append(f"🔥 **{p.user.display_name} 受到 1 點燃燒傷害！(剩餘 {p.burn_turns} 回合)**")
                
            if shrink_level > 0:
                if p.x < min_bound or p.x > max_bound or p.y < min_bound or p.y > max_bound:
                    p.hp -= 1
                    log.append(f"☠️ {p.user.display_name} 身處毒氣中，受到 1 點傷害！")

        if self.p1.hp <= 0 and self.p2.hp <= 0:
            log.append("\n **雙方同時倒下，遊戲平手！**")
            return {"status": "over", "log": log}
        elif self.p1.hp <= 0:
            log.append(f"\n **{self.p2.user.mention} 獲得勝利！**")
            return {"status": "over", "log": log}
        elif self.p2.hp <= 0:
            log.append(f"\n **{self.p1.user.mention} 獲得勝利！**")
            return {"status": "over", "log": log}
        
        self.turns_since_last_item += 1
        if random.random() < 0.20 or self.turns_since_last_item >= 5:
            available_spots = [(x, y) for x in range(self.board_size) for y in range(self.board_size) 
                               if (x, y) not in [(self.p1.x, self.p1.y), (self.p2.x, self.p2.y)] and (x, y) not in self.items_on_board]
            if available_spots:
                pos = random.choice(available_spots)
                new_item = random.choice(["暗黑穿越", "燃燒彈", "冰凍術", "傷害加倍球", "回血心"])
                self.items_on_board[pos] = new_item
                self.turns_since_last_item = 0
                log.append(f"⭐ **地圖上出現了 {new_item}！**")

        self.fire_zones.clear()
        
        self.p1.action_submitted = False
        self.p2.action_submitted = False
        
        for p in [self.p1, self.p2]:
            p.gun_hit_enemy = False
            p.is_shielded = False
            p.has_reflected = False
            p.is_frozen = False
            
            if p.selected_card in p.cards:
                p.cards.remove(p.selected_card)
                p.cards.append(random.choice(["刀", "槍", "盾"]))
                
        self.turn_count += 1
        return {"status": "continue", "log": log}


# --- Discord UI 介面 ---

class GridBladeButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🗡️", style=discord.ButtonStyle.secondary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        if view.main_view.game_over: return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
        if interaction.user != view.player.user: return await interaction.response.send_message("這不是你的面板！", ephemeral=True)
        if view.player.action_submitted: return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)
        if "刀" not in view.player.cards: return await interaction.response.send_message("你手牌裡沒有【刀】！請換一個。", ephemeral=True)

        is_valid, msg = view.main_view.engine.validate_and_set_action(view.player, "刀", self.direction)
        if not is_valid: return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

        await interaction.response.edit_message(content=f"✅ 第 {view.main_view.engine.turn_count} 回合行動已鎖定：【刀】！\n請等待結算...", view=view)
        await view.main_view.check_both_submitted()

class GridShieldButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🛡️", style=discord.ButtonStyle.success, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        if view.main_view.game_over: return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
        if interaction.user != view.player.user: return await interaction.response.send_message("這不是你的面板!", ephemeral=True)
        if view.player.action_submitted: return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)
        if "盾" not in view.player.cards: return await interaction.response.send_message("你手牌裡沒有【盾】！請換一個。", ephemeral=True)

        is_valid, msg = view.main_view.engine.validate_and_set_action(view.player, "盾", self.direction)
        if not is_valid: return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

        await interaction.response.edit_message(content=f"✅ 第 {view.main_view.engine.turn_count} 回合行動已鎖定：【盾】！\n請等待結算...", view=view)
        await view.main_view.check_both_submitted()

class GridSpearButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="📌", style=discord.ButtonStyle.primary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        if view.main_view.game_over: return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
        if interaction.user != view.player.user: return await interaction.response.send_message("這不是你的面板！", ephemeral=True)
        if view.player.action_submitted: return await interaction.response.send_message("你已經出招了，請等待對手！", ephemeral=True)
        if "槍" not in view.player.cards: return await interaction.response.send_message("你手牌裡沒有【槍】！請換一個。", ephemeral=True)

        await interaction.response.send_modal(GunDistanceModal(view.player, self.direction, view.main_view, view, view.main_view.engine.turn_count))

class GunDistanceModal(discord.ui.Modal):
    dist_input = discord.ui.TextInput(
        label='衝刺距離 (1-4)', placeholder='輸入 1~4', required=True, max_length=1
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
        if self.main_view.game_over: return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
        if self.player.action_submitted or self.main_view.engine.turn_count != self.turn_count:
            return await interaction.response.send_message("回合已過或已出招！", ephemeral=True)

        try:
            dist = int(self.dist_input.value)
            if dist < 1 or dist > 4: raise ValueError 
        except ValueError:
            return await interaction.response.send_message("輸入格式錯誤！距離需為 1~4。", ephemeral=True)

        is_valid, msg = self.main_view.engine.validate_and_set_action(self.player, "槍", self.direction, dist)
        if not is_valid: return await interaction.response.send_message(f"不能出界ㄛ!：{msg}", ephemeral=True)

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
        if view.main_view.game_over: return await interaction.response.send_message("遊戲結束ㄌ!", ephemeral=True)
        if interaction.user != view.player.user: return await interaction.response.send_message("這不是你的面板！", ephemeral=True)

        view.main_view.game_over = True
        if view.main_view.timer_task: view.main_view.timer_task.cancel()

        loser = interaction.user
        winner = view.main_view.engine.p2 if loser == view.main_view.engine.p1.user else view.main_view.engine.p1

        view.main_view.last_log = [f"🏳️ **{loser.mention} 投降！**\n **{winner.user.mention} 獲得勝利！**"]
        
        await interaction.response.edit_message(content="你輸ㄌ。", view=view)
        await view.main_view.safe_edit_main_message()


class ItemFixedButton(discord.ui.Button):
    def __init__(self, item_name, row, emoji, player):
        super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.item_name = item_name
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        view: ControlPanel = self.view
        p = view.player
        
        if view.main_view.game_over: 
            return await interaction.response.send_message("遊戲結束了ㄌ！", ephemeral=True)
        if interaction.user != p.user: 
            return await interaction.response.send_message("這不是你的面板！", ephemeral=True)
        
        if self.item_name not in p.items:
            return await interaction.response.send_message(f"你沒有 {self.item_name}！", ephemeral=True)
        
        await interaction.response.send_modal(TargetingModal(p, self.item_name, view))


class TargetingModal(discord.ui.Modal):
    coord_input = discord.ui.TextInput(
        label='目標座標 (先輸入橫的 X，再直的 Y)', 
        placeholder='例如 34 代表橫的 3，直的 4', 
        min_length=2, max_length=2, required=True
    )

    def __init__(self, player, item_name, control_view):
        super().__init__(title=f'使用道具：{item_name}')
        self.player = player
        self.item_name = item_name
        self.control_view = control_view

    async def on_submit(self, interaction: discord.Interaction):
        if self.control_view.main_view.game_over: return await interaction.response.send_message("遊戲結束了！", ephemeral=True)

        raw_val = self.coord_input.value
        try:
            target_x = int(raw_val[0])
            target_y = int(raw_val[1])
            if not (0 <= target_x < 10 and 0 <= target_y < 10): raise ValueError
        except:
            return await interaction.response.send_message("座標格式錯誤！請輸入兩位數字(00-99)。", ephemeral=True)

        if self.item_name in ["燃燒彈", "冰凍術"]:
            self.player.queued_items.append((self.item_name, target_x, target_y))
            self.player.items.remove(self.item_name)
            await interaction.response.edit_message(content=f"✅ 已準備 {self.item_name}！請繼續選擇你的出牌（刀/槍/盾/暗黑穿越）。", view=ControlPanel(self.control_view.main_view, self.player))

        elif self.item_name == "暗黑穿越":
            if self.player.action_submitted:
                return await interaction.response.send_message("你這回合已經出過招了，無法再使用暗黑穿越！", ephemeral=True)
            
            self.player.selected_card = "暗黑穿越"
            self.player.target_x = target_x
            self.player.target_y = target_y
            self.player.action_submitted = True
            
            # 暗黑穿越的瞬移距離一樣記錄，並同步更新面向
            self.player.move_dx = target_x - self.player.x
            self.player.move_dy = target_y - self.player.y
            dx, dy = self.player.move_dx, self.player.move_dy
            if abs(dy) > abs(dx):
                self.player.facing = "UP" if dy < 0 else "DOWN"
            elif abs(dx) > abs(dy):
                self.player.facing = "LEFT" if dx < 0 else "RIGHT"
            elif dx != 0:
                self.player.facing = "LEFT" if dx < 0 else "RIGHT"
            
            self.player.items.remove(self.item_name)
            
            await self.control_view.main_view.safe_edit_main_message()
            await interaction.response.edit_message(content=f"✅ 行動已鎖定：【暗黑穿越】！\n請等待結算...", view=ControlPanel(self.control_view.main_view, self.player))
            await self.control_view.main_view.check_both_submitted()


# --- 隱藏操控面板 (25格排滿完美利用) ---
class ControlPanel(discord.ui.View):
    def __init__(self, main_view, player):
        super().__init__(timeout=None)
        self.main_view = main_view
        self.player = player

        # --- Row 0 --- 
        self.add_item(ItemFixedButton("暗黑穿越", 0, "✴️", self.player))
        self.add_item(GridBladeButton(8, 0))
        self.add_item(GridSpearButton(4, 0)) 
        self.add_item(GridBladeButton(1, 0))
        self.add_item(ItemFixedButton("燃燒彈", 0, "🧨", self.player))

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
        self.add_item(ItemFixedButton("冰凍術", 4, "🧊", self.player))
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
            await asyncio.sleep(25)
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
        
        p1 = Player(interaction.user, 2, 2)
        p2 = Player(opponent, 7, 7)
        engine = BGSGameEngine(p1, p2)
        view = BGSMainView(engine)
        
        await interaction.followup.send(view.get_message_content(), view=view)
        view.message = await interaction.original_response()
        
        view.timer_task = asyncio.create_task(view.start_timer())

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))