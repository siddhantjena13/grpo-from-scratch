import torch
import torch.nn.functional as F


def get_logprobs(model, input_ids, attention_mask):
    logits = model(input_ids=input_ids, attention_mask=attention_mask).logits

    shifted_logits = logits[:, :-1, :]
    shifted_ids = input_ids[:, 1:]

    log_probs = F.log_softmax(shifted_logits, dim=-1)

    token_logprobs = torch.gather(
        log_probs, dim=-1, index=shifted_ids.unsqueeze(-1)
    ).squeeze(-1)

    return token_logprobs

def build_completion_mask(input_ids, prompt_len, pad_token_id):
    B, T = input_ids.shape

    shifted_ids = input_ids[:, 1:]

    positions = torch.arange(1, T, device=input_ids.device).unsqueeze(0)
    is_completion = positions >= prompt_len

    not_pad = shifted_ids != pad_token_id

    return (is_completion & not_pad).float()

def grpo_loss(new_logprobs, old_logprobs, ref_logprobs, advantages, mask,
              clip_eps=0.2, beta=0.04):
    ratio = torch.exp(new_logprobs - old_logprobs)
    adv = advantages.unsqueeze(1)

    surr1 = ratio * adv
    surr2 = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * adv

    policy_loss = -torch.min(surr1, surr2)
    kl = kl_penalty(new_logprobs, ref_logprobs)

    per_token_loss = policy_loss + beta * kl

    return (per_token_loss * mask).sum() / mask.sum()

def kl_penalty(new_logprobs, ref_logprobs):
    diff = ref_logprobs - new_logprobs
    return torch.exp(diff) - diff - 1.0


if __name__ == "__main__":
    new = torch.randn(2, 5)
    adv = torch.tensor([1.0, 1.0])
    mask = torch.ones(2, 5)

    print(grpo_loss(new, new.clone(), new.clone(), adv, mask))   # expect -1.0
    print(grpo_loss(new, new.clone(), new + 0.5, adv, mask))     # expect > -1.0