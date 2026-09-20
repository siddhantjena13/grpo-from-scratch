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

if __name__ == "__main__":
    policy, ref, tokenizer, optimizer = setup()

    rng = random.Random(0)
    numbers, target = make_problem(rng)
    print("problem:", numbers, "->", target)

    r = rollout(policy, tokenizer, numbers, target, G=4, max_new_tokens=200)

    print("sequences:  ", r["sequences"].shape)
    print("mask:       ", r["mask"].shape)
    print("old_logprobs:", r["old_logprobs"].shape)
    print("tokens per completion:", r["mask"].sum(dim=1).tolist())
    print("rewards:", r["rewards"])
    print("\n--- sample ---\n", r["texts"][0][:300])

def update(policy, ref, optimizer, batch, G, beta=0.04, clip_eps=0.2):
    advantages = compute_advantages(batch["rewards"], G)
    advantages = torch.tensor(advantages, device=policy.device, dtype=torch.float32)

    with torch.no_grad():
        ref_logprobs = get_logprobs(ref, batch["sequences"], batch["attention_mask"])

    new_logprobs = get_logprobs(policy, batch["sequences"], batch["attention_mask"])

    loss = grpo_loss(
        new_logprobs, batch["old_logprobs"], ref_logprobs,
        advantages, batch["mask"], clip_eps=clip_eps, beta=beta,
    )

    optimizer.zero_grad()
    loss.backward()
    grad_norm = torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=1.0)
    optimizer.step()

    return loss.item(), grad_norm.item()