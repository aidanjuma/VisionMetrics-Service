from dataclasses import dataclass
from typing import List


@dataclass
class GPUInstanceSplit:
    """
    Represents a split of a GPU into multiple instances.
    Splits one physical GPU into multiple partitions, each of which can be used and allocated independently.
    """

    split_ratios: List[int]

    def __post_init__(self):
        if sum(self.split_ratios) != 100:
            raise ValueError('Split ratios must sum to 100')
        if not all(ratio > 0 for ratio in self.split_ratios):
            raise ValueError('All split ratios must be positive integers.')
