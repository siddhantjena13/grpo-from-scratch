import copy
import random
import torch

from grpo.generate import load_model_and_tokenizer, generate, PROMPT_TEMPLATE
from grpo.countdown import reward, make_problem
from grpo.advantages import compute_advantages
from grpo.loss import get_logprobs, build_completion_mask, grpo_loss


def setup(lr=1e-6):
    policy, tokenizer = load_model_and_tokenizer()

    ref = copy.deepcopy(policy)
    for p in ref.parameters():
        p.requires_grad_(False)
    ref.eval()

    policy.eval()
    optimizer = torch.optim.AdamW(policy.parameters(), lr=lr)

    return policy, ref, tokenizer, optimizer

def rollout(policy, tokenizer, numbers, target, G=4, max_new_tokens=400):
    question = PROMPT_TEMPLATE.format(
        numbers=", ".join(str(n) for n in numbers), target=target
    )

    out = generate(policy, tokenizer, question, G=G, max_new_tokens=max_new_tokens)

    rewards = [reward(t, numbers, target) for t in out["texts"]]

    mask = build_completion_mask(
        out["sequences"], out["prompt_len"], tokenizer.pad_token_id
    )

    with torch.no_grad():
        old_logprobs = get_logprobs(
            policy, out["sequences"], out["attention_mask"]
        )

    return {
        "sequences": out["sequences"],
        "attention_mask": out["attention_mask"],
        "mask": mask,
        "old_logprobs": old_logprobs,
        "rewards": rewards,
        "texts": out["texts"],
    }