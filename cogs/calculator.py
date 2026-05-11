import discord
from discord.ext import commands
from discord import app_commands
import sympy
import re
import math
import logging
from sympy.parsing.sympy_parser import (
    parse_expr, 
    standard_transformations, 
    implicit_multiplication_application, 
    convert_xor, 
    factorial_notation
)
from typing import Optional

# ==========================================
# 語法教學表 (純數值計算限定)
# ==========================================
HELP_TEXT = """**【 純數值計算機指南 】**
`.=` (前綴) 或 `/calc`：純數字計算機。

**【 基礎運算與內建常數 】**
* **基礎運算**：加減乘除與取餘 `+`, `-`, `*`, `/`, `%`
* **次方 / 階乘**：`^` 或 `**`  |  `!`
* **圓周率**：`pi` 或 `π`
* **自然對數底數**：`e`
* **黃金比例**：`phi` 或 `φ`
* **無限大**：`oo` 或 `∞` (兩個小寫的 o)
* **虛數**：`I` 或 `i`

**【 函數大全 】**
* **對數**：預設底數10 `log(真數)` | 自訂底數 `log(真數, 底數)` | 自然對數 `ln(真數)`
* **根號 / 絕對值**：平方根 `sqrt(x)` | 立方根 `cbrt(x)` | 絕對值 `abs(x)`
* **三角函數**：`sin()`, `cos()`, `tan()`, `sec()`, `csc()`, `cot()`
* **反三角函數**：`asin()`, `acos()`, `atan()`
* **雙曲函數**：`sinh()`, `cosh()`, `tanh()`"""

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

    # 完美數字格式化
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
            # 特例直接轉字串
            return str(val)

    # 核心計算模組 (純數字限定)
    def evaluate(self, expr_str):
        # 1. 基礎清理與長度限制
        if len(expr_str) > 500:
            return False, "太長ㄌ"

        expr_str = expr_str.replace('×', '*').replace('÷', '/').replace('％', '%')
        temp_expr = expr_str.replace('^', '**').replace(' ', '')

        # 2. 🛡️ 精準防禦：位數預估法 (防止 9**9**9 導致記憶體崩潰)
        power_patterns = re.findall(r'(\d+)\*\*(\d+(?:\*\*\d+)?)', temp_expr)
        for base, exp_part in power_patterns:
            try:
                if '**' in exp_part:
                    sub_base, sub_exp = exp_part.split('**')
                    actual_exp = int(sub_base) ** int(sub_exp)
                else:
                    actual_exp = int(exp_part)
                
                if int(base) > 0:
                    digits = actual_exp * math.log10(int(base))
                    if digits > 1000000:
                        return True, "`∞`"
            except OverflowError:
                return True, "`∞`"
            except Exception:
                pass 

        # 3. 準備純數字運算環境
        local_dict = {
            # 內建常數
            'e': sympy.E, 'pi': sympy.pi, 'π': sympy.pi,
            'phi': sympy.GoldenRatio, 'φ': sympy.GoldenRatio,
            'oo': sympy.oo, '∞': sympy.oo, 'max': sympy.oo, 'min': -sympy.oo,
            'I': sympy.I, 'i': sympy.I,

            # 對數、開根號、絕對值
            'log': log10, 'ln': sympy.ln,
            'sqrt': sympy.sqrt, 'cbrt': sympy.cbrt, 
            'abs': sympy.Abs,
            
            # 三角函數全家餐
            'sin': sympy.sin, 'cos': sympy.cos, 'tan': sympy.tan,
            'sec': sympy.sec, 'csc': sympy.csc, 'cot': sympy.cot,
            
            # 反三角函數
            'asin': sympy.asin, 'acos': sympy.acos, 'atan': sympy.atan,
            
            # 雙曲函數
            'sinh': sympy.sinh, 'cosh': sympy.cosh, 'tanh': sympy.tanh,
        }

        try:
            # 攔截等號 (純運算不需要等號)
            if '=' in expr_str:
                return False, "算式怎麼有等於鴨"
            
            expr = parse_expr(expr_str, local_dict=local_dict, transformations=self.transformations)
            
            # 嚴格攔截未知數：如果算式包含未定義的字母，直接擋下
            if expr.free_symbols:
                return False, "看不懂鴨，有亂打常數嗎?"
            
            # 執行計算
            val = expr.evalf()
            return True, f"`{self.format_number(val)}`"
                
        except Exception as e:
            return False, f"看不懂鴨，沒打錯嗎? ({str(e)})"

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
        
        success, result = self.evaluate(expr)
        if success:
            await message.reply(f"`{expr}`\n{result}")
        else:
            await message.reply(f"{result}")

    # 極簡化斜線指令 (/calc)
    @app_commands.command(name="calc", description="計算機")
    @app_commands.describe(expression="輸入算式 (留空則顯示語法教學)")
    async def calc(self, interaction: discord.Interaction, expression: Optional[str] = None):
        # 如果沒填算式，就當作他想看說明書
        if not expression:
            await interaction.response.send_message(HELP_TEXT)
            return

        success, result = self.evaluate(expression)
        if success:
            await interaction.response.send_message(f"`{expression}`\n{result}")
        else:
            await interaction.response.send_message(f"{result}", ephemeral=True)

    # 攔截並過濾掉因為 `.=` 產生的「找不到指令」報錯
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            # 檢查找不到的指令是不是以 '=' 開頭 (例如 =, =e2/e3)
            if ctx.invoked_with and ctx.invoked_with.startswith("="):
                return # 靜默忽略，不報錯

        # 其他常規錯誤照常透過 logger 輸出，避免把真的 bug 也吃掉了
        logger = logging.getLogger('discord.ext.commands.bot')
        logger.error('Ignoring exception in command %s', ctx.command, exc_info=error)

async def setup(bot):
    await bot.add_cog(Calculator(bot))