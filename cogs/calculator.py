import discord
from discord.ext import commands
from discord import app_commands
import sympy
import re
import math
from sympy.parsing.sympy_parser import (
    parse_expr, 
    standard_transformations, 
    implicit_multiplication_application, 
    convert_xor, 
    factorial_notation
)
from typing import Optional

# ==========================================
# 語法教學表 (純文字常數)
# ==========================================
HELP_TEXT = """**【 運算模式指南 】**
`.=` (前綴)：僅限「純數值」計算。算加減乘除、數字極限、求具體數值 (禁止輸入未知數)。
`/calc` (純數值計算)：同上，但使用指令觸發。
`/calc` (代數運算)：支援英文字母 (x, y, n)。化簡、展開、因式分解、微積分。
`/calc` (解方程式)：找未知數專用。必須有等號 (=)，可用逗號解聯立。

**【 基礎運算與常數 】**
加減乘除與取餘：`+`, `-`, `*`, `/`, `%`
次方：`^` 或 `**`
階乘：`!`
圓周率：`pi` 或 `π`
自然對數底數：`e`
無限大：`oo` 或 `∞` (兩個小寫的 o)
虛數：`I` 或 `i`

**【 函數大全 】**
對數 (預設底數10)：`log(真數)`
對數 (自訂底數)：`log(真數, 底數)`
自然對數 (底數 e)：`ln(真數)`
平方根 / 立方根：`sqrt(x)` / `cbrt(x)`
三角函數：`sin()`, `cos()`, `tan()`, `sec()`, `csc()`, `cot()`
反三角函數：`asin()`, `acos()`, `atan()`
雙曲函數：`sinh()`, `cosh()`, `tanh()`

**【 代數與微積分 】** (需使用 /calc 選擇代數運算)
代數化簡：直接輸入算式 (例: `(x+y)^2 - 2xy`)
多項式展開：`expand(算式)`
因式分解：`factor(算式)`
微分：`diff(算式, 變數)`
不定積分：`int(算式, 變數)`
定積分 / 瑕積分：`int(算式, (變數, 下限, 上限))`
極限：`limit(算式, 變數, 趨近值)`
級數總和 (Σ)：`sum(算式, (變數, 起點, 終點))`

**【 解方程式 】** (需使用 /calc 選擇解方程式，算式必須包含等號)
解一元方程式：`x^2 - 5x + 6 = 0`
解聯立方程式：`x + y = 10, x - y = 2`
解未知數等式：`2x + 5 = 15`"""

# 自訂一個「以 10 為底」的 log 函數
class log10(sympy.Function):
    @classmethod
    def eval(cls, x):
        return sympy.log(x, 10)

class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # SymPy 翻譯規則
        self.transformations = (standard_transformations +
                                (implicit_multiplication_application,) +
                                (convert_xor,) +
                                (factorial_notation,))

    # 完美數字格式化 (消除多餘的 .0，支援處理 NaN, 無限大, 與複數)
    def format_number(self, val):
        if val == sympy.oo or val == sympy.zoo: return "∞"
        if val == -sympy.oo: return "-∞"
        if val is sympy.nan: return "NaN (無解或未定義的數學式)"
        
        try:
            # 處理純實數
            if val.is_real:
                f_val = round(float(val), 10)
                if f_val.is_integer():
                    return str(int(f_val))
                return str(f_val)
            # 處理虛數/複數
            return str(val.evalf(10)).replace('.0*I', '*I').replace('1.0*I', 'I')
        except Exception:
            # 代數或特例直接轉字串
            return str(val)

    # 核心計算模組
    def evaluate(self, expr_str, mode="calc"):
        # 1. 基礎清理與長度限制
        if len(expr_str) > 500:
            return False, "算式長度過長，請縮短一點。"

        expr_str = expr_str.replace('×', '*').replace('÷', '/').replace('％', '%')
        temp_expr = expr_str.replace('^', '**').replace(' ', '')

        # 2. 🛡️ 精準防禦：位數預估法 (防止 9**9**9 或 2**1000000 導致記憶體崩潰)
        # 找出所有 a**b 的結構
        power_patterns = re.findall(r'(\d+)\*\*(\d+(?:\*\*\d+)?)', temp_expr)
        for base, exp_part in power_patterns:
            try:
                # 處理嵌套次方，如 9**9**9
                if '**' in exp_part:
                    sub_base, sub_exp = exp_part.split('**')
                    actual_exp = int(sub_base) ** int(sub_exp)
                else:
                    actual_exp = int(exp_part)
                
                # 計算結果大約會有幾位數：log10(base^exp) = exp * log10(base)
                if int(base) > 0:
                    digits = actual_exp * math.log10(int(base))
                    # 如果位數超過 1,000,000 位，這絕對會讓 Python 記憶體溢位
                    if digits > 1000000:
                        return True, "`∞` (數值過大，已超越硬體極限)"
            except OverflowError:
                # 如果連指數自己都溢位了，那結果絕對是無限大
                return True, "`∞`"
            except Exception:
                pass # 複雜代數或包含未知數的式子，直接放行交給 SymPy 處理

        # 3. 準備 SymPy 運算環境
        # 註冊未知數 (加入 n，用於數列或極限)
        x, y, z, n = sympy.symbols('x y z n')
        
        # 👑 終極技能庫：把所有神級函數全部綁定
        local_dict = {
            # 變數與常數
            'x': x, 'y': y, 'z': z, 'n': n,
            'e': sympy.E, 'pi': sympy.pi, 'π': sympy.pi,
            'oo': sympy.oo, '∞': sympy.oo, 'max': sympy.oo, 'min': -sympy.oo,
            'I': sympy.I, 'i': sympy.I, # 支援無限大與虛數 i

            # 對數與開根號
            'log': log10, 'ln': sympy.ln,
            'sqrt': sympy.sqrt, 'cbrt': sympy.cbrt, # 平方根與立方根
            
            # 三角函數全家餐
            'sin': sympy.sin, 'cos': sympy.cos, 'tan': sympy.tan,
            'sec': sympy.sec, 'csc': sympy.csc, 'cot': sympy.cot,
            
            # 反三角函數
            'asin': sympy.asin, 'acos': sympy.acos, 'atan': sympy.atan,
            
            # 雙曲函數
            'sinh': sympy.sinh, 'cosh': sympy.cosh, 'tanh': sympy.tanh,
            
            # 微積分與高階代數
            'diff': sympy.diff,               # 微分
            'int': sympy.integrate,           # 積分
            'limit': sympy.limit,             # 極限
            'sum': sympy.summation,           # 數列級數和 (Σ)
            'factor': sympy.factor,           # 因式分解
            'expand': sympy.expand,           # 多項式展開
            'simplify': sympy.simplify        # 強制化簡
        }

        try:
            # ==================================
            # 模式 3：解方程式 (找未知數)
            # ==================================
            if mode == "solve":
                if '=' not in expr_str:
                    return False, "解方程式需要等號 (=)，例如：2x^2 - 8 = 0"
                
                equations = []
                parts = expr_str.split(',')
                for part in parts:
                    if '=' in part:
                        left_str, right_str = part.split('=', 1)
                        left_expr = parse_expr(left_str, local_dict=local_dict, transformations=self.transformations)
                        right_expr = parse_expr(right_str, local_dict=local_dict, transformations=self.transformations)
                        equations.append(sympy.Eq(left_expr, right_expr))
                
                solution = sympy.solve(equations)
                return True, f"`{solution}`"

            if '=' in expr_str:
                return False, "純運算模式不支援等號！若要解未知數，請用 `/calc` 選擇「解方程式找未知數」。"
            
            expr = parse_expr(expr_str, local_dict=local_dict, transformations=self.transformations)
            
            # ==================================
            # 模式 1：純計算 (.= 限定)
            # ==================================
            if mode == "calc":
                if expr.free_symbols:
                    return False, "純計算模式不支援保留英文字母。若要算微積分或代數化簡，請使用 `/calc` 選擇「代數運算」。"
                val = expr.evalf()
                return True, f"`{self.format_number(val)}`"
            
            # ==================================
            # 模式 2：代數運算與微積分
            # ==================================
            elif mode == "algebra":
                # 直接針對使用者輸入的特殊函數（如因式分解、極限）執行化簡
                simplified = sympy.simplify(expr)
                if not simplified.free_symbols:
                    return True, f"`{self.format_number(simplified.evalf())}`"
                return True, f"`{simplified}`"
                
        except Exception as e:
            return False, f"看不懂，請檢查括號與函數用法 ({str(e)})"

    # ==========================================
    # Discord 介面綁定
    # ==========================================

    # 文字頻道監聽器 (.= 指令)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content.startswith(".="):
            return
        expr = message.content[2:].strip()
        if not expr: return
        
        success, result = self.evaluate(expr, mode="calc")
        if success:
            await message.reply(f"`{expr}`\n{result}")
        else:
            await message.reply(f"{result}")

    # 斜線指令 (/calc)
    @app_commands.command(name="calc", description="終極工程計算機 (支援微積分、解方程式與教學)")
    @app_commands.describe(mode="選擇你要的計算類型", expression="輸入算式 (若查看介紹可不填)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="📖 查看語法介紹與教學", value="help"),
        app_commands.Choice(name="純數值計算(限數值, 含極限與虛數)", value="calc"),
        app_commands.Choice(name="代數運算(微積分, 展開, 因式分解)", value="algebra"),
        app_commands.Choice(name="解方程式找未知數(支援多變數)", value="solve"),
    ])
    async def calc(self, interaction: discord.Interaction, mode: app_commands.Choice[str], expression: Optional[str] = None):
        # 攔截教學模式，直接輸出設定好的說明文字
        if mode.value == "help":
            await interaction.response.send_message(HELP_TEXT)
            return
            
        # 若不是看教學，卻沒填算式，給予提示
        if not expression:
            await interaction.response.send_message("請輸入你要計算的算式！", ephemeral=True)
            return

        success, result = self.evaluate(expression, mode=mode.value)
        if success:
            await interaction.response.send_message(f"`{expression}`\n{result}")
        else:
            await interaction.response.send_message(f"{result}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Calculator(bot))