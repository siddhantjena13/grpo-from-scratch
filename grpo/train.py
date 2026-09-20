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