import sys
from grpo.train import train

CONFIGS = {
    "baseline": dict(max_new_tokens=300),
    "long":     dict(max_new_tokens=600),
    "binary":   dict(max_new_tokens=300, reward_mode="binary", num_steps=150),
    "g4":       dict(max_new_tokens=300, G=4),
    "g16":      dict(max_new_tokens=300, G=16),
    "nokl":     dict(max_new_tokens=300, beta=0.0),
    "binwarm":  dict(max_new_tokens=300, reward_mode="binary", num_steps=300,
                     init_ckpt="runs/baseline/latest.pt"),
}

if __name__ == "__main__":
    name = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    cfg = dict(num_steps=500, G=8, checkpoint_every=25, seed=seed) | CONFIGS[name]
    run_name = name if seed == 0 else f"{name}_s{seed}"
    train(run_name=run_name, **cfg)
