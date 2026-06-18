import simpleeval
import re
import math
from decimal import Decimal, ROUND_HALF_UP

# Create a custom simple_eval instance with math functions and constants
def create_evaluator():
    functions = simpleeval.DEFAULT_FUNCTIONS.copy()
    functions.update({
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan
    })
    
    names = simpleeval.DEFAULT_NAMES.copy()
    names.update({
        'pi': math.pi,
        'e': math.e
    })
    
    return simpleeval.SimpleEval(functions=functions, names=names)

evaluator = create_evaluator()


def evaluate_math(expression: str):
    """
    Safely evaluate a mathematical expression.
    Returns the integer result or None if it's invalid.
    """
    try:
        # Strip leading zeros to prevent python SyntaxError
        expression = re.sub(r'(?<!\.)\b0+(?=\d)', '', expression)
        result = evaluator.eval(expression)
        if isinstance(result, (int, float)):
            return int(Decimal(str(result)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return None
    except Exception:
        return None

def parse_message(content: str):
    """
    Returns a dict with various parsing flags.
    """
    content = content[:6]
    
    base_result = {
        "is_number": False,
        "value": None,
        "is_troll_text": False,
        "is_spam": False,
        "is_calculus": False,
        "is_trig": False,
        "is_constant": False,
        "is_long_math": False,
        "raw_eval_string": ""
    }
    
    # Calculus check (even if spaced out)
    if re.search(r'\b(int|integral|diff|dx|dy|d/dx)\b', content.lower()) or '∫' in content:
        base_result["is_calculus"] = True
        return base_result

    # Quick troll checks before anything else
    if content.startswith("O") and len(content) > 1 and content[1].isdigit():
        base_result["is_troll_text"] = True
        return base_result
    if content.startswith("I") and len(content) > 1 and content[1].isdigit():
        base_result["is_troll_text"] = True
        return base_result
    if content.startswith("_ _") and re.search(r'\d', content):
        base_result["is_troll_text"] = True
        return base_result
        
    parts = content.split()
    if not parts:
        return base_result
        
    first_part = parts[0]
    
    # Check for "5word", "5👀", "5:eyes:" style trolling (digits immediately followed by letters/emojis/symbols without space)
    if re.match(r'^\d+[^0-9\+\-\*/\(\)\.\s]+.*$', first_part):
        base_result["is_troll_text"] = True
        return base_result

    # Clean the first part from trailing symbols if they are not part of math
    val = evaluate_math(first_part)
    
    if val is not None:
        ops_count = sum(first_part.count(op) for op in ['+', '-', '*', '/', '**'])
        is_spam = first_part.count("+1") > 1
        
        base_result.update({
            "is_number": True,
            "value": val,
            "is_spam": is_spam,
            "is_long_math": ops_count > 10,
            "is_trig": bool(re.search(r'\b(sin|cos|tan)\b', first_part.lower())),
            "is_constant": bool(re.search(r'\b(pi|e)\b', first_part.lower())),
            "raw_eval_string": first_part
        })
        
    return base_result
