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
        board = [["🔲" for _ in range(self.board_size)] for _ in range(self.board_size)]
        if self.p1.x == self.p2.x and self.p1.y == self.p2.y:
            board[self.p1.y][self.p1.x] = "🩸"
        else:
            board[self.p1.y][self.p1.x] = "🐶"
            board[self.p2.y][self.p2.x] = "🐱"
            
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
            log.append("🩸 **雙方目標為同一格，觸發近距離廝殺！卡牌效果全部失效！**")
            self.p1.x, self.p1.y = p1_t
            self.p2.x, self.p2.y = p2_t
            return self._resolve_clash(log)

        # 2. 刀、盾移動
        for p in [self.p1, self.p2]:
            if p.selected_card in ["刀", "盾"]:
                p.x, p.y = p.target_x, p.target_y
                name_display = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
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
                        log.append(f"🎯 {p_name} 衝刺撞到對手，緊急煞車於 ({p.x}, {p.y})")
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
                p_name = "🐶 " + p.user.display_name if p == self.p1 else "🐱 " + p.user.display_name
                e_name = "🐶 " + enemy.user.display_name if enemy == self.p1 else "🐱 " + enemy.user.display_name
                
                if enemy.is_shielded:
                    reflect = int(dmg * 0.5)
                    p.hp -= reflect
                    log.append(f"🛡️ {e_name} 的盾牌反彈了攻擊！{p_name} 受到 {reflect} 點反傷！")
                else:
                    enemy.hp -= dmg
                    log.append(f"⚔️ {p_name} 命中了！對 {e_name} 造成 {dmg} 點傷害！")

    def _end_turn(self, log: list):
        if self.p1.hp <= 0 and self.p2.hp <= 0:
            log.append("\n💀 **雙方同時倒下，遊戲平手！**")
            return {"status": "over", "log": log}
        elif self.p1.hp <= 0:
            log.append(f"\n🏆 **{self.p2.user.mention} 獲得勝利！**")
            return {"status": "over", "log": log}
        elif self.p2.hp <= 0:
            log.append(f"\n🏆 **{self.p1.user.mention} 獲得勝利！**")
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

class GridBladeButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🗡️", style=discord.ButtonStyle.secondary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: BGSMainView = self.view
        current_actor = view.get_current_actor()
        if interaction.user != current_actor.user:
            await interaction.response.send_message("❌ 現在不是你的回合，不是你！", ephemeral=True)
            return
            
        # 暗中防呆：沒這張牌只會彈出警告，對手看不見
        if "刀" not in current_actor.cards:
            await interaction.response.send_message("❌ 你手牌裡沒有【刀】！請換一個。", ephemeral=True)
            return

        is_valid, msg = view.engine.validate_and_set_action(current_actor, "刀", self.direction)
        if not is_valid:
            await interaction.response.send_message(f"❌ 撞牆啦！無效路線：{msg}", ephemeral=True)
            return

        await view.process_action_submission(interaction)

class GridShieldButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="🛡️", style=discord.ButtonStyle.success, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: BGSMainView = self.view
        current_actor = view.get_current_actor()
        if interaction.user != current_actor.user:
            await interaction.response.send_message("❌ 現在不是你的回合，不是你！", ephemeral=True)
            return
            
        # 暗中防呆
        if "盾" not in current_actor.cards:
            await interaction.response.send_message("❌ 你手牌裡沒有【盾】！請換一個。", ephemeral=True)
            return

        is_valid, msg = view.engine.validate_and_set_action(current_actor, "盾", self.direction)
        if not is_valid:
            await interaction.response.send_message(f"❌ 撞牆啦！無效路線：{msg}", ephemeral=True)
            return

        await view.process_action_submission(interaction)

class GridSpearButton(discord.ui.Button):
    def __init__(self, direction, row):
        super().__init__(label="\u200b", emoji="📌", style=discord.ButtonStyle.primary, row=row)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        view: BGSMainView = self.view
        current_actor = view.get_current_actor()
        if interaction.user != current_actor.user:
            await interaction.response.send_message("❌ 現在不是你的回合，不是你！", ephemeral=True)
            return
            
        # 暗中防呆
        if "槍" not in current_actor.cards:
            await interaction.response.send_message("❌ 你手牌裡沒有【槍】！請換一個。", ephemeral=True)
            return

        # 彈出 Modal 要求輸入距離 (對手看不到)
        await interaction.response.send_modal(GunDistanceModal(current_actor, self.direction, view, view.engine.turn_count))

class GunDistanceModal(discord.ui.Modal):
    dist_input = discord.ui.TextInput(
        label='衝刺距離 (1-9)', placeholder='輸入 1~9', required=True, max_length=1
    )

    def __init__(self, player, direction, main_view, turn_count):
        dir_names = {1: "向下", 2: "向右", 3: "向左", 4: "向上"}
        super().__init__(title=f'設定槍的衝刺距離 ({dir_names[direction]})')
        self.player = player
        self.direction = direction
        self.main_view = main_view
        self.turn_count = turn_count

    async def on_submit(self, interaction: discord.Interaction):
        current_actor = self.main_view.get_current_actor()
        if current_actor != self.player or self.main_view.engine.turn_count != self.turn_count:
            await interaction.response.send_message("❌ 回合已過或不是你！", ephemeral=True)
            return

        try:
            dist = int(self.dist_input.value)
            if dist < 1 or dist > 9:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("輸入格式錯誤！距離需為 1~9。", ephemeral=True)
            return

        is_valid, msg = self.main_view.engine.validate_and_set_action(self.player, "槍", self.direction, dist)
        if not is_valid:
            await interaction.response.send_message(f"❌ 撞牆啦！無效行動：{msg}", ephemeral=True)
            return

        await self.main_view.process_action_submission(interaction)

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
        view: BGSMainView = self.view
        if interaction.user not in [view.engine.p1.user, view.engine.p2.user]:
            await interaction.response.send_message("❌ 觀戰者不能幫忙投降！", ephemeral=True)
            return

        view.game_over = True
        if view.timer_task:
            view.timer_task.cancel()

        loser = interaction.user
        winner = view.engine.p2 if loser == view.engine.p1.user else view.engine.p1

        view.last_log = [f"🏳️ **{loser.mention} 舉白旗投降！**\n🏆 **{winner.user.mention} 獲得勝利！**"]
        view.update_buttons()
        await interaction.response.edit_message(content=view.get_message_content(), view=view)


class BGSMainView(discord.ui.View):
    def __init__(self, engine: BGSGameEngine):
        super().__init__(timeout=None)
        self.engine = engine
        self.message = None
        self.timer_task = None
        self.game_over = False
        self.last_log = ["⚔️ **《刀槍盾》生死鬥開始！** ⚔️\n(雙方盲出武器與座標，同時結算！)"]
        
        self.update_buttons()

    def get_current_actor(self):
        if not self.engine.p1.action_submitted: return self.engine.p1
        if not self.engine.p2.action_submitted: return self.engine.p2
        return None

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
            curr_p = self.get_current_actor()
            if curr_p:
                p_emoji = "🐶" if curr_p == self.engine.p1 else "🐱"
                full_text += f"\n\n➡️ **現在輪到 {p_emoji} {curr_p.user.mention} 選擇行動 (限時30秒)**"
                full_text += "\n直接點擊下方對應的武器圖示即可盲出行動！(沒有對應武器請勿點擊)"

        return full_text

    def update_buttons(self):
        self.clear_items()
        if self.game_over:
            return

        curr_p = self.get_current_actor()
        if not curr_p: return 

        # 取消變灰防呆，所有的按鈕一律保持 disabled=False
        # 第 0 排 (最上方)
        self.add_item(GridEmptyButton(0))
        self.add_item(GridBladeButton(8, 0))
        self.add_item(GridSpearButton(4, 0)) # 向上 4
        self.add_item(GridBladeButton(1, 0))
        self.add_item(GridEmptyButton(0))

        # 第 1 排
        self.add_item(GridBladeButton(7, 1))
        self.add_item(GridShieldButton(7, 1))
        self.add_item(GridShieldButton(8, 1))
        self.add_item(GridShieldButton(1, 1))
        self.add_item(GridBladeButton(2, 1))

        # 第 2 排 (中間排)
        self.add_item(GridSpearButton(3, 2)) # 向左 3
        self.add_item(GridShieldButton(6, 2))
        self.add_item(GridCenterButton(2, curr_p, self.engine)) # 中間頭像
        self.add_item(GridShieldButton(2, 2))
        self.add_item(GridSpearButton(2, 2)) # 向右 2

        # 第 3 排
        self.add_item(GridBladeButton(6, 3))
        self.add_item(GridShieldButton(5, 3))
        self.add_item(GridShieldButton(4, 3))
        self.add_item(GridShieldButton(3, 3))
        self.add_item(GridBladeButton(3, 3))

        # 第 4 排 (最下方)
        self.add_item(GridEmptyButton(4))
        self.add_item(GridBladeButton(5, 4))
        self.add_item(GridSpearButton(1, 4)) # 向下 1
        self.add_item(GridBladeButton(4, 4))
        self.add_item(GridSurrenderButton(4)) # 右下角放投降

    async def start_timer(self):
        turn_now = self.engine.turn_count
        actor_now = self.get_current_actor()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return 
            
        if not self.game_over and self.engine.turn_count == turn_now and self.get_current_actor() == actor_now:
            self.engine.force_random_action(actor_now)
            await self.process_action_submission(timeout_actor=actor_now)

    async def process_action_submission(self, interaction: discord.Interaction = None, timeout_actor: Player = None):
        current_task = asyncio.current_task()
        if self.timer_task and self.timer_task != current_task:
            self.timer_task.cancel()

        timeout_msg = None
        if timeout_actor:
            timeout_msg = f"⏳ **{timeout_actor.user.display_name} 思考超時！系統已強制隨機代打！**"

        if self.engine.p1.action_submitted and self.engine.p2.action_submitted:
            # 雙方皆已提交，同時結算！
            res = self.engine.resolve_turn()
            self.last_log = res["log"]
            if timeout_msg:
                self.last_log.insert(1, timeout_msg)
            if res["status"] == "over":
                self.game_over = True
        else:
            # P1 已提交，換 P2
            if timeout_msg:
                self.last_log = [timeout_msg, f"✅ **{self.engine.p1.user.display_name}** 已鎖定行動，換 **{self.engine.p2.user.display_name}** 選擇！"]
            else:
                self.last_log = [f"✅ **{self.engine.p1.user.display_name}** 已鎖定行動，換 **{self.engine.p2.user.display_name}** 選擇！"]

        self.update_buttons()
        content = self.get_message_content()
        
        if interaction:
            await interaction.response.edit_message(content=content, view=self)
        else:
            await self.message.edit(content=content, view=self)

        if not self.game_over:
            self.timer_task = asyncio.create_task(self.start_timer())


class BladeGunShieldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bgs", description="發起一場刀槍盾對決！(5x5盲出預判、同時結算)")
    async def start_bgs(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("對不起鴨，我不會玩", ephemeral=True)
            return
        
        p1 = Player(interaction.user, 0, 0)
        p2 = Player(opponent, 9, 9)
        engine = BGSGameEngine(p1, p2)
        view = BGSMainView(engine)
        
        await interaction.response.send_message(view.get_message_content(), view=view)
        view.message = await interaction.original_response()
        
        view.timer_task = asyncio.create_task(view.start_timer())

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))