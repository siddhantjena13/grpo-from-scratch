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

def train(num_steps=50, G=4, max_new_tokens=200, seed=0, log_every=1):
    policy, ref, tokenizer, optimizer = setup()
    rng = random.Random(seed)

    for step in range(num_steps):
        numbers, target = make_problem(rng)
        batch = rollout(policy, tokenizer, numbers, target,
                        G=G, max_new_tokens=max_new_tokens)
        loss, grad_norm = update(policy, ref, optimizer, batch, G=G)

        rewards = batch["rewards"]
        lengths = batch["mask"].sum(dim=1)
        degenerate = len(set(rewards)) == 1

        if step % log_every == 0:
            print(
                f"step {step:3d} | "
                f"reward {sum(rewards)/len(rewards):.3f} | "
                f"max {max(rewards):.2f} | "
                f"loss {loss:+.4f} | "
                f"grad {grad_norm:.2f} | "
                f"len {lengths.float().mean():.0f} | "
                f"{'FLAT' if degenerate else '    '}"
            )
    
if __name__ == "__main__":
    train(num_steps=3, G=4, max_new_tokens=200)