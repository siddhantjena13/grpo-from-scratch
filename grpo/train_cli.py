from grpo.train import train

if __name__ == "__main__":
    train(num_steps=500, G=8, max_new_tokens=300,
          checkpoint_every=25, run_name="baseline")
