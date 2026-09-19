import re

ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)


def extract_answer(completion: str) -> str | None:
    matches = ANSWER_RE.findall(completion)
    if not matches:
        return None
    return matches[-1].strip()

import ast

ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def safe_eval(expr: str) -> float | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    return _eval_node(tree.body)


def _eval_node(node) -> float | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BINOPS):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            return None
        return left / right

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _eval_node(node.operand)
        return None if val is None else -val

    return None

if __name__ == "__main__":
    print(safe_eval("9 * 5 + 10 * 2"))      # 65.0
    print(safe_eval("(10 + 9) * 5"))        # 95.0
    print(safe_eval("10 / 0"))              # None
    print(safe_eval("__import__('os')"))    # None
    print(safe_eval("9 * 5 +"))             # None