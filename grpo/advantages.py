import math


def compute_advantages(rewards: list[float], G: int) -> list[float]:
    advantages = []

    # Each consecutive run of G rewards belongs to one prompt.
    for i in range(0, len(rewards), G):
        group = rewards[i : i + G]

        mean = sum(group) / len(group)
        variance = sum((r - mean) ** 2 for r in group) / len(group)
        std = math.sqrt(variance)

        # All completions scored the same -> no signal in this group.
        if std == 0.0:
            advantages.extend([0.0] * len(group))
        else:
            advantages.extend((r - mean) / std for r in group)

    return advantages


if __name__ == "__main__":
    print(compute_advantages([1, 0, 0, 1], G=4))
    print(compute_advantages([0.5, 0.5, 0.5, 0.5], G=4))
    print(compute_advantages([1, 0, 0, 1, 0.3, 0.3, 0.3, 1.0], G=4))