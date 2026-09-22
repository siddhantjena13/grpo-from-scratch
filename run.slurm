#!/bin/bash
#SBATCH --job-name=grpo-baseline
#SBATCH --account=socialrl
#SBATCH --partition=gpu-l40s
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=8:00:00
#SBATCH --requeue
#SBATCH --output=logs/%j.out

cd /gscratch/stf/$USER/grpo-from-scratch
export HF_HOME=/gscratch/stf/$USER/hf_cache
export UV_CACHE_DIR=/gscratch/stf/$USER/cache/uv
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
uv run python -m grpo.train_cli "$@"
