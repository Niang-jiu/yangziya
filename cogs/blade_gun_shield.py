import discord
from discord.ext import commands
import random

# --- 核心邏輯與資料結構 ---

class Player:
    def __init__(self, user: discord.Member, x: int, y: int):
        self.user = user
        self.hp = 10
        self.initial_hp = 10
        self.x = x
        self.y = y
        self.has_damage_buff = False
        self.cards = ["刀", "槍", "盾"] # 初始三張卡
        self.action_ready = False
        
        # 暫存本回合的行動
        self.selected_card = None
        self.selected_dir = None
        self.selected_steps = None
        
        # 狀態標記
        self.is_shielded = False

class BGSGameEngine:
    def __init__(self, player1: Player, player2: Player):
        self.board_size = 10
        self.p1 = player1
        self.p2 = player2
        self.turn_count = 1
        
        # 方位映射 (1:上, 2:右上, 3:右, 4:右下, 5:下, 6:左下, 7:左, 8:左上)
        self.dir_map = {
            1: (0, -1), 2: (1, -1), 3: (1, 0), 4: (1, 1),
            5: (0, 1), 6: (-1, 1), 7: (-1, 0), 8: (-1, -1)
        }
        
        # 象棋「馬」(刀) 的 8 種走法，對應 1~8 的選擇，並決定「面向」
        # 假設 1,2 面向上; 3,4 面向右; 5,6 面向下; 7,8 面向左
        self.knight_map = {
            1: (-1, -2, "UP"), 2: (1, -2, "UP"),
            3: (2, -1, "RIGHT"), 4: (2, 1, "RIGHT"),
            5: (1, 2, "DOWN"), 6: (-1, 2, "DOWN"),
            7: (-2, 1, "LEFT"), 8: (-2, -1, "LEFT")
        }

    def resolve_turn(self):
        """執行回合結算：移動 -> 碰撞 -> 攻擊 -> 補卡"""
        
        # 1. 執行移動
        self._move_player(self.p1)
        self._move_player(self.p2)

        # 2. 判斷同格碰撞 (Clash)
        if self.p1.x == self.p2.x and self.p1.y == self.p2.y:
            clash_result = self._resolve_clash(self.p1, self.p2)
            # 若碰撞導致有人死亡，直接結束並回傳結果
            if clash_result["status"] == "win":
                return clash_result
        else:
            # 3. 若無同格，執行攻擊與判定 (盾的反彈也在這裡處理)
            self._resolve_attacks()

        # 檢查是否有人血量歸零
        if self.p1.hp <= 0 or self.p2.hp <= 0:
            return self._check_win_condition()

        # 4. 回合結束，雙方各盲抽一張卡 (刀/槍/盾 隨機)
        self.p1.cards.append(random.choice(["刀", "槍", "盾"]))
        self.p2.cards.append(random.choice(["刀", "槍", "盾"]))
        self.turn_count += 1
        
        # 清除本回合狀態
        self._reset_player_turn_state(self.p1)
        self._reset_player_turn_state(self.p2)
        
        return {"status": "continue"}

    def _move_player(self, p: Player):
        """處理玩家的移動邏輯"""
        if p.selected_card == "刀":
            dx, dy, facing = self.knight_map[p.selected_dir]
            p.x = max(0, min(self.board_size - 1, p.x + dx))
            p.y = max(0, min(self.board_size - 1, p.y + dy))
            p.facing = facing
            
        elif p.selected_card == "槍":
            dx, dy = self.dir_map[p.selected_dir]
            steps = p.selected_steps
            enemy = self.p2 if p == self.p1 else self.p1
            
            # 實作直線移動，遇到敵人停在前面
            for _ in range(steps):
                next_x, next_y = p.x + dx, p.y + dy
                if next_x == enemy.x and next_y == enemy.y:
                    break # 撞到敵人，停在上一格
                if 0 <= next_x < self.board_size and 0 <= next_y < self.board_size:
                    p.x, p.y = next_x, next_y
                else:
                    break # 撞牆
            p.facing = p.selected_dir
            
        elif p.selected_card == "盾":
            dx, dy = self.dir_map[p.selected_dir]
            p.x = max(0, min(self.board_size - 1, p.x + dx))
            p.y = max(0, min(self.board_size - 1, p.y + dy))
            p.is_shielded = True

    def _resolve_clash(self, player_a: Player, player_b: Player):
        """帶入你設計的近距離廝殺邏輯"""
        player_a.initial_hp = player_a.hp
        player_b.initial_hp = player_b.hp

        dmg_by_a = 2 if player_a.has_damage_buff else 1
        dmg_by_b = 2 if player_b.has_damage_buff else 1

        for i in range(1, 6):
            player_a.hp -= dmg_by_b
            player_b.hp -= dmg_by_a

            if player_a.hp <= 0 and player_b.hp <= 0:
                if player_a.initial_hp > player_b.initial_hp:
                    return {"status": "win", "winner": player_a, "reason": "近距離廝殺：雙方歸零，初始血量較高"}
                elif player_b.initial_hp > player_a.initial_hp:
                    return {"status": "win", "winner": player_b, "reason": "近距離廝殺：雙方歸零，初始血量較高"}
                else:
                    return {"status": "draw", "reason": "近距離廝殺：雙方歸零且初始血量相同，平手"}
            elif player_a.hp <= 0:
                return {"status": "win", "winner": player_b, "reason": "近距離廝殺擊殺對手"}
            elif player_b.hp <= 0:
                return {"status": "win", "winner": player_a, "reason": "近距離廝殺擊殺對手"}

        return {"status": "survive"}

    def _resolve_attacks(self):
        """處理非同格時的攻擊與盾牌反彈邏輯"""
        # 實作刀的前方 3*2 判定與槍的直線判定
        # 並且檢查被攻擊方是否為 is_shielded，如果是且在九宮格內，觸發 0.5 倍反傷
        # ... (此處保留給詳細的座標範圍數學運算) ...
        pass

    def _check_win_condition(self):
        if self.p1.hp <= 0 and self.p2.hp <= 0:
            return {"status": "draw", "reason": "雙方同時倒下！"}
        elif self.p1.hp <= 0:
            return {"status": "win", "winner": self.p2, "reason": "血量歸零"}
        else:
            return {"status": "win", "winner": self.p1, "reason": "血量歸零"}

    def _reset_player_turn_state(self, p: Player):
        p.action_ready = False
        p.selected_card = None
        p.selected_dir = None
        p.selected_steps = None
        p.is_shielded = False

# --- Discord Cog 模組 ---

class BladeGunShieldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {} # 儲存進行中的遊戲 {channel_id: GameEngine}

    @commands.command(name="bgs")
    async def start_bgs(self, ctx, opponent: discord.Member):
        """發起一場刀槍盾對決！"""
        if opponent.bot or opponent == ctx.author:
            await ctx.send("無效的對手！")
            return
        
        # 建立玩家與遊戲引擎 (初始座標設定在對角)
        p1 = Player(ctx.author, 0, 0)
        p2 = Player(opponent, 9, 9)
        game = BGSGameEngine(p1, p2)
        self.active_games[ctx.channel.id] = game
        
        await ctx.send(f"⚔️ **《刀槍盾》對決開始！** ⚔️\n{p1.user.mention} VS {p2.user.mention}\n請雙方點擊下方按鈕私密選擇行動！")
        
        # 這裡會呼叫自定義的 discord.ui.View
        # await self.send_action_ui(ctx.channel, game)

    # UI 視窗回呼函式：當雙方都選擇完畢後觸發
    async def on_players_ready(self, channel_id):
        game = self.active_games.get(channel_id)
        if not game: return
        
        # 執行結算
        result = game.resolve_turn()
        
        # 根據 result 渲染戰鬥過程與更新地圖...
        # ...

async def setup(bot):
    await bot.add_cog(BladeGunShieldCog(bot))