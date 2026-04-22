import discord
from discord.ext import commands
from discord import app_commands
import ast
import operator
import math

# 支援的運算符號
ALLOWED_OPERATORS = {
    ast.Add: operator.add,     # +
    ast.Sub: operator.sub,     # -
    ast.Mult: operator.mul,    # *
    ast.Div: operator.truediv, # /
    ast.Mod: operator.mod,     # %
    ast.UAdd: operator.pos,    # 正號
    ast.USub: operator.neg,    # 負號
    ast.Pow: operator.pow      # 次方 (**)
}

# --- 新增這個自訂的階乘函數 ---
def safe_factorial(n):
    # 檢查這個數字是不是整數 (例如 5.0)
    if float(n).is_integer():
        if n < 0:
            raise ValueError("階乘不支援負數！")
        # 把 float 轉回 int 餵給 Python
        return math.factorial(int(n))
    raise ValueError("階乘只能計算整數！")

# 支援的數學函數 (把原本的 math.factorial 換掉)
ALLOWED_FUNCTIONS = {
    'log': math.log10,          # log() 預設為以10為底
    'ln': math.log,             # ln() 為自然對數 (以e為底)
    'factorial': safe_factorial # 使用我們自訂的安全階乘
}


# 支援的數學常數
ALLOWED_CONSTANTS = {
    'e': math.e,
    'pi': math.pi,
    'π': math.pi
}

# 處理字串中的階乘符號 (!) 轉換為 factorial()
def process_factorial(expr: str) -> str:
    res = ""
    for char in expr:
        if char == '!':
            j = len(res) - 1
            # 如果前面是括號，就往回找對應的左括號
            if j >= 0 and res[j] == ')':
                parens = 1
                j -= 1
                while j >= 0 and parens > 0:
                    if res[j] == ')': parens += 1
                    elif res[j] == '(': parens -= 1
                    j -= 1
                operand = res[j+1:]
                res = res[:j+1] + f"factorial({operand})"
            # 如果前面是數字或變數，就提取出來
            else:
                while j >= 0 and (res[j].isalnum() or res[j] in '._'):
                    j -= 1
                operand = res[j+1:]
                res = res[:j+1] + f"factorial({operand})"
        else:
            res += char
    return res

# 安全的算式解析與計算函數
def evaluate_math(expression: str):
    # 1. 替換全形、特殊符號與空白，新增對 ^ 的支援
    expression = (expression
                  .replace('×', '*')
                  .replace('÷', '/')
                  .replace('％', '%')
                  .replace('^', '**')  # 支援 2^3
                  .replace(' ', ''))
    
    # 2. 處理階乘符號 (將 5! 變成 factorial(5))
    expression = process_factorial(expression)
    
    try:
        # 將字串解析為語法結構樹
        tree = ast.parse(expression, mode='eval')
    except SyntaxError:
        raise ValueError("?")

    # 遞迴計算每個節點
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                try:
                    return float(node.value)
                except OverflowError:
                    return float('inf')
            raise ValueError("不知道")
            
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            
            if op_type not in ALLOWED_OPERATORS:
                raise ValueError("看不懂")
            
            # 防呆：除以 0 或取餘數為 0
            if op_type in (ast.Div, ast.Mod) and right == 0:
                raise ZeroDivisionError("不會")
            
            # 防呆：避免超大指數運算卡死機器人
            if op_type == ast.Pow:
                if right > 10000 or left > 10000:
                    return float('inf')
            
            try:
                return ALLOWED_OPERATORS[op_type](left, right)
            except OverflowError:
                return float('inf')
            
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op_type = type(node.op)
            return ALLOWED_OPERATORS[op_type](operand)
            
        # 支援常數 (e, pi, π)
        elif isinstance(node, ast.Name):
            if node.id in ALLOWED_CONSTANTS:
                return ALLOWED_CONSTANTS[node.id]
            raise ValueError("看不懂")
            
        # 支援函數呼叫 (log, ln, factorial)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("不支援的函數格式")
            func_name = node.func.id
            if func_name not in ALLOWED_FUNCTIONS:
                raise ValueError(f"看不懂函數: {func_name}")
            
            args = [_eval(arg) for arg in node.args]
            try:
                return ALLOWED_FUNCTIONS[func_name](*args)
            except Exception as e:
                # 攔截例如 factorial(2.5) 這種無法計算的狀況
                raise ValueError(f"函數無法計算 ({e})")
                
        else:
            raise ValueError("我不會")

    return _eval(tree)


class Calculator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="calc", description="計算機")
    @app_commands.describe(expression="輸入算式 (例如: log(100) + π * 2!)")
    async def calc(self, interaction: discord.Interaction, expression: str):
        await self.process_calculation(interaction, expression)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.content.startswith(".="):
            expression = message.content[2:].strip()
            if not expression:
                return

            await self.process_calculation(message, expression)

    async def process_calculation(self, context, expression: str):
        try:
            result = evaluate_math(expression)
            
            if math.isinf(result):
                final_result = "∞"
            else:
                final_result = round(result, 10)
                if final_result.is_integer():
                    final_result = int(final_result)
                        
            response_text = f"`{expression}` = `{final_result}`"
            
            if isinstance(context, discord.Interaction):
                await context.response.send_message(response_text)
            else:
                await context.reply(response_text)
            
        except ZeroDivisionError as e:
            await self.send_error(context, f"{e}")
        except ValueError as e:
            await self.send_error(context, f"{e}")
        # 這裡原本沒有 as e，我幫你補上了，否則遇到未定義錯誤時會當機
        except Exception as e:
            await self.send_error(context, f"{e}")

    async def send_error(self, context, error_msg: str):
        if isinstance(context, discord.Interaction):
            await context.response.send_message(error_msg, ephemeral=True)
        else:
            await context.reply(error_msg)

async def setup(bot):
    await bot.add_cog(Calculator(bot))