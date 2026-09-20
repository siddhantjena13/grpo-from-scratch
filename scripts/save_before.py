import random
import torch

from grpo.generate import load_model_and_tokenizer, generate, PROMPT_TEMPLATE
from grpo.countdown import reward, make_problem

N_PROBLEMS = 10
G = 4
SEED = 1234


def main():
    model, tokenizer = load_model_and_tokenizer()
    rng = random.Random(SEED)

    lines = ["# Completions before training\n"]
    lines.append(f"Model: Qwen/Qwen2.5-0.5B-Instruct  \n")
    lines.append(f"Eval seed: {SEED}, {N_PROBLEMS} problems, G={G}\n")

    all_rewards = []

    for i in range(N_PROBLEMS):
        numbers, target = make_problem(rng)
        question = PROMPT_TEMPLATE.format(
            numbers=", ".join(str(n) for n in numbers), target=target
        )
        out = generate(model, tokenizer, question, G=G, max_new_tokens=400)
        rewards = [reward(t, numbers, target) for t in out["texts"]]
        all_rewards.extend(rewards)

        lines.append(f"\n## Problem {i}: {numbers} -> {target}\n")
        for j, (text, r) in enumerate(zip(out["texts"], rewards)):
            lines.append(f"\n### completion {j} — reward {r}\n")
            lines.append(f"```\n{text.strip()}\n```\n")

        print(f"problem {i}: {numbers} -> {target}  rewards {rewards}")

    mean = sum(all_rewards) / len(all_rewards)
    solve_rate = sum(r == 1.0 for r in all_rewards) / len(all_rewards)
    lines.insert(3, f"\n**Mean reward: {mean:.3f}  |  Solve rate: {solve_rate:.1%}**\n")

    with open("results/completions_before.md", "w") as f:
        f.writelines(lines)

    print(f"\nmean reward {mean:.3f} | solve rate {solve_rate:.1%}")


if __name__ == "__main__":
    main()