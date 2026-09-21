# grpo-from-scratch

A from-scratch implementation of **GRPO** (Group Relative Policy Optimization, from DeepSeekMath) in PyTorch, training a small language model to solve Countdown arithmetic puzzles.

No RL libraries. The environment, reward, advantages, loss, and training loop are all written by hand as small, independently tested functions.

> **Status: work in progress.** The training loop runs end to end and reward goes up. Ablations and after-training evaluation are next.

## The task

Countdown: given four numbers and a target, write an arithmetic expression that uses each number exactly once and equals the target.

```
Numbers: [3, 7, 9, 12]   Target: 48
<answer>9 * 7 - 12 - 3</answer>   ← the model must produce this format
```

Problems are generated backwards (build a random expression, use its value as the target), so every puzzle is solvable.

**Reward** is a partial-credit ladder:

| Reward | Condition |
|---|---|
| 0.0 | No `<answer>` tags |
| 0.1 | Tags present, expression unparseable |
| 0.3 | Valid expression, wrong numbers |
| 0.5 | Right numbers, wrong value |
| 1.0 | Correct |

Expressions are evaluated by walking the Python AST and allowing only `+ - * /` on numeric constants. `eval()` is never called on model output.

## How it works

For each prompt, sample a **group** of G completions. Each completion's advantage is its reward relative to its siblings:

```
advantage_i = (reward_i - mean(group)) / std(group)
```

The group itself is the baseline, so there's no critic network. Groups where every completion gets the same reward have zero advantage and produce no learning signal (logged as `FLAT`).

The loss is the PPO clipped surrogate, plus a KL penalty to a frozen copy of the starting model (k3 estimator), averaged over completion tokens only.

## Layout

```
grpo/
  countdown.py    environment: problem generator, answer parsing, safe eval, reward
  advantages.py   group-relative advantages
  loss.py         token log-probs, completion mask, KL penalty, GRPO loss
  generate.py     model loading and sampling (HuggingFace transformers)
  train.py        rollout → update loop, metrics, checkpoints
  train_cli.py    baseline run config
scripts/
  save_before.py  evaluate the untrained model on held-out problems
run.slurm         cluster launcher
```

## Running

```bash
uv sync
uv run python -m grpo.loss            # unit check on the loss math
uv run python -m grpo.train           # 3-step smoke test
uv run python -m grpo.train_cli       # full baseline run (500 steps)
uv run python scripts/save_before.py  # baseline eval
```

Each run writes `runs/<name>/config.json`, `metrics.jsonl` (one line per step), and `latest.pt`.

**Model:** `Qwen/Qwen2.5-0.5B-Instruct`. Chosen over Qwen3-0.6B because it has no thinking mode to suppress.

## Results so far

**Before training** (10 held-out problems, 4 samples each): mean reward 0.068, **0/40 solved**.

**Baseline run** (500 steps, G=8, max 300 new tokens, lr 1e-6, β=0.04, ε=0.2, on one L40s):

| | First 50 steps | Last 50 steps |
|---|---|---|
| Mean reward | 0.044 | 0.287 |

Reward rose about 6.5x. However, max reward in the final steps never exceeded 0.5, and completion length fell from ~230 tokens to ~40–100. The likely explanation is that the model learned to collect partial credit (short, well-formatted answers using the right numbers) without learning to hit the target. This hasn't been confirmed yet: it needs a read of the post-training completions.

18 of 500 steps (3.6%) were FLAT at G=8, versus 60% of problems at G=4 before training. This is not a clean comparison, since the model changed during training.

## Practical notes

**Memory.** Log-probs are computed as `logit[token] - logsumexp(logits)` rather than a full `log_softmax`, which avoids materializing a second vocabulary-sized tensor (~2GB saved at G=8).

A 0.5B model still did not fit on an 11GB RTX 2080 Ti. That card has no bf16 support, so the model loads in fp32: policy (~2GB), frozen reference (~2GB), gradients (~2GB), and Adam state (~4GB) total ~10GB before any activations. Reducing G can't fix that. The standard fixes would be 8-bit Adam, fp16, or keeping the reference model on CPU. The baseline ran on a 48GB L40s instead.

**Cluster (UW Hyak).** Compute nodes' system Python lacks `Python.h`, which Triton needs to compile. Use a uv-managed interpreter: `uv venv --python 3.12 --python-preference only-managed`.

## Known issues

- `pad_token = eos_token`, so real end-of-sequence tokens are masked out of the loss. The model gets no credit for choosing to stop.
- `<answer>1</answer>` earns 0.1 for no effort, which is an obvious reward-hacking target.
- The problem generator evaluates left to right, ignoring operator precedence. Targets are reachable, just not necessarily by the generated expression.
- Loss is averaged per token, so longer completions carry more weight.
- Gradient norms sit around 10–20 and are clipped to 1.0 on nearly every step.
- Checkpoints are saved but training doesn't resume from them yet.

## Next

- [ ] Evaluate the trained checkpoint → `results/completions_after.md`
- [ ] Ablations: group size G, KL coefficient β, clip ε, group normalization, partial-credit vs. binary reward
- [ ] Plots of reward, FLAT rate, and completion length over training
- [ ] Resume from checkpoint