import sys
from grpo.train import train

CONFIGS = {
    "baseline": dict(max_new_tokens=300),
    "long":     dict(max_new_tokens=600),
    "binary":   dict(max_new_tokens=300, reward_mode="binary", num_steps=150),
}

if __name__ == "__main__":
    name = sys.argv[1]
    cfg = dict(num_steps=500, G=8, checkpoint_every=25) | CONFIGS[name]
    train(run_name=name, **cfg)
