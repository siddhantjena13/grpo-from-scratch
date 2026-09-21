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

def extract_numbers(expr: str) -> list[float] | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    numbers = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                numbers.append(float(node.value))
            else:
                return None
    return numbers


def uses_numbers_exactly(expr: str, allowed: list[int]) -> bool:
    used = extract_numbers(expr)
    if used is None:
        return False
    return sorted(used) == sorted(float(n) for n in allowed)

def reward(completion: str, numbers: list[int], target: int) -> float:
    answer = extract_answer(completion)
    if answer is None:
        return 0.0

    value = safe_eval(answer)
    if value is None:
        return 0.1

    if not uses_numbers_exactly(answer, numbers):
        return 0.3

    if abs(value - target) < 1e-6:
        return 1.0
    return 0.5

import random

def make_problem(rng: random.Random, n_numbers: int = 4) -> tuple[list[int], int]:
    while True:
        numbers = [rng.randint(1, 20) for _ in range(n_numbers)]
        value = float(numbers[0])
        for n in numbers[1:]:
            op = rng.choice(["+", "-", "*"])
            if op == "+":
                value += n
            elif op == "-":
                value -= n
            else:
                value *= n
        if 10 <= value <= 200:
            return numbers, int(value)

if __name__ == "__main__":
    rng = random.Random(0)
    for _ in range(5):
        print(make_problem(rng))

def binary_reward(text, numbers, target):
    return 1.0 if reward(text, numbers, target) == 1.0 else 0.0
