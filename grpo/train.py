import copy
import json
import os
import random

import torch

from grpo.generate import load_model_and_tokenizer, generate, PROMPT_TEMPLATE
from grpo.countdown import reward, make_problem
from grpo.advantages import compute_advantages
from grpo.loss import get_logprobs, build_completion_mask, grpo_loss


def setup(lr=1e-6):
    policy, tokenizer = load_model_and_tokenizer()

    # Frozen snapshot of the starting weights. The KL term measures drift
    # away from this; it is never updated.
    ref = copy.deepcopy(policy)
    for p in ref.parameters():
        p.requires_grad_(False)
    ref.eval()

    # eval() only disables dropout -- gradients still flow normally.
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

    # The policy's opinion of its own tokens AT GENERATION TIME. Must be
    # captured now, before any weight update, or the ratio is always 1.
    with torch.no_grad():
        old_logprobs = get_logprobs(policy, out["sequences"], out["attention_mask"])

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

    # The only forward pass that builds a gradient graph.
    new_logprobs = get_logprobs(policy, batch["sequences"], batch["attention_mask"])

    loss = grpo_loss(
        new_logprobs,
        batch["old_logprobs"],
        ref_logprobs,
        advantages,
        batch["mask"],
        clip_eps=clip_eps,
        beta=beta,
    )

    optimizer.zero_grad()
    loss.backward()
    grad_norm = torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=1.0)
    optimizer.step()

    return loss.item(), grad_norm.item()


def save_checkpoint(policy, optimizer, step, out_dir):
    torch.save(
        {
            "step": step,
            "model": policy.state_dict(),
            "optimizer": optimizer.state_dict(),
        },
        f"{out_dir}/latest.pt",
    )


def train(
    num_steps=50,
    G=4,
    max_new_tokens=200,
    seed=0,
    log_every=1,
    checkpoint_every=25,
    beta=0.04,
    clip_eps=0.2,
    lr=1e-6,
    run_name="baseline",
    runs_root="runs",
):
    out_dir = f"{runs_root}/{run_name}"
    os.makedirs(out_dir, exist_ok=True)

    config = {
        "num_steps": num_steps,
        "G": G,
        "max_new_tokens": max_new_tokens,
        "seed": seed,
        "beta": beta,
        "clip_eps": clip_eps,
        "lr": lr,
        "run_name": run_name,
    }
    with open(f"{out_dir}/config.json", "w") as f:
        json.dump(config, f, indent=2)
    print(f"run: {out_dir}  config: {config}", flush=True)

    policy, ref, tokenizer, optimizer = setup(lr=lr)
    rng = random.Random(seed)

    metrics_path = f"{out_dir}/metrics.jsonl"

    for step in range(num_steps):
        numbers, target = make_problem(rng)
        batch = rollout(
            policy, tokenizer, numbers, target, G=G, max_new_tokens=max_new_tokens
        )
        loss, grad_norm = update(
            policy, ref, optimizer, batch, G=G, beta=beta, clip_eps=clip_eps
        )

        rewards = batch["rewards"]
        lengths = batch["mask"].sum(dim=1)
        # No spread in the group -> all advantages are zero -> nothing learned.
        degenerate = (max(rewards) - min(rewards)) < 1e-9

        metrics = {
            "step": step,
            "reward": sum(rewards) / len(rewards),
            "max_reward": max(rewards),
            "loss": loss,
            "grad_norm": grad_norm,
            "mean_len": lengths.float().mean().item(),
            "flat": bool(degenerate),
        }

        with open(metrics_path, "a") as f:
            f.write(json.dumps(metrics) + "\n")

        if step % log_every == 0:
            print(
                f"step {step:4d} | "
                f"reward {metrics['reward']:.3f} | "
                f"max {metrics['max_reward']:.2f} | "
                f"loss {loss:+.4f} | "
                f"grad {grad_norm:6.2f} | "
                f"len {metrics['mean_len']:.0f} | "
                f"{'FLAT' if degenerate else '    '}",
                flush=True,
            )

        if step % checkpoint_every == 0 or step == num_steps - 1:
            save_checkpoint(policy, optimizer, step, out_dir)

    print(f"done. metrics -> {metrics_path}", flush=True)


if __name__ == "__main__":
    train(num_steps=3, G=4, max_new_tokens=200, run_name="smoke")