import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

PROMPT_TEMPLATE = """Using the numbers {numbers} exactly once each and the operators + - * / (and parentheses), write an expression that equals {target}.

Think briefly, then give your final answer inside <answer></answer> tags, like this:
<answer>(3 + 4) * 2</answer>"""


def load_model_and_tokenizer(model_name=MODEL_NAME):
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    if device == "cuda" and torch.cuda.is_bf16_supported():
        dtype = torch.bfloat16
    else:
        dtype = torch.float32

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name, dtype=dtype)
    model = model.to(device)
    model.eval()

    return model, tokenizer

def build_prompt(tokenizer, question):
    messages = [{"role": "user", "content": question}]
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

def generate(model, tokenizer, question, G=4, max_new_tokens=400, temperature=1.0):
    prompt = build_prompt(tokenizer, question)

    inputs = tokenizer([prompt] * G, return_tensors="pt", padding=True)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=1.0,
            pad_token_id=tokenizer.pad_token_id,
        )

    prompt_len = inputs["input_ids"].shape[1]

    return {
        "sequences": outputs,                                   # (G, T) prompt + completion
        "attention_mask": (outputs != tokenizer.pad_token_id).long(),
        "prompt_len": prompt_len,
        "texts": [tokenizer.decode(row[prompt_len:], skip_special_tokens=True)
                  for row in outputs],
    }

if __name__ == "__main__":
    model, tokenizer = load_model_and_tokenizer()

    question = PROMPT_TEMPLATE.format(numbers="2, 5, 9, 10", target=65)

    for i, c in enumerate(generate(model, tokenizer, question, max_new_tokens=400)):
        print(f"--- {i} ---\n{c}\n")