import discord
from discord.ext import commands
from discord import app_commands
import sympy
from sympy.parsing.sympy_parser import (
    parse_expr, 
    standard_transformations, 
    implicit_multiplication_application, 
    convert_xor, 
    factorial_notation
)

# 自訂一個「以 10 為底」的 log 函數，解決 SymPy 預設把 log 當成 ln 的問題
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

    # 完美數字格式化 (支援處理 NaN, 無限大, 與複數)
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
        expr_str = expr_str.replace('×', '*').replace('÷', '/').replace('％', '%')
        
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
            
            # 反三角函數 (arcsin, arccos...)
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
                return False, "純運算模式不支援等號！若要解未知數，請用 `/calc` 選擇「解方程式」。"
            
            expr = parse_expr(expr_str, local_dict=local_dict, transformations=self.transformations)
            
            # ==================================
            # 模式 1：純計算 (.= 限定)
            # ==================================
            if mode == "calc":
                if expr.free_symbols:
                    return False, "純計算模式不支援保留英文字母。若要算微積分或代數，請使用 `/calc` 選擇「代數運算」。"
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

    # 文字頻道監聽器
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
    @app_commands.command(name="calc", description="計算機")
    @app_commands.describe(expression="輸入算式", mode="選擇你要的計算類型")
    @app_commands.choices(mode=[
        app_commands.Choice(name="純數值計算(限數值, 含極限與虛數)", value="calc"),
        app_commands.Choice(name="代數運算(微積分, 展開, 因式分解)", value="algebra"),
        app_commands.Choice(name="解方程式找未知數(支援多變數)", value="solve"),
    ])
    async def calc(self, interaction: discord.Interaction, expression: str, mode: app_commands.Choice[str]):
        success, result = self.evaluate(expression, mode=mode.value)
        if success:
            await interaction.response.send_message(f"`{expression}`\n{result}")
        else:
            await interaction.response.send_message(f"{result}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Calculator(bot))