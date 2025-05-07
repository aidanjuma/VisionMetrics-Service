from dataclasses import dataclass
from typing import Any


@dataclass
class ManagedGpuInstance:
    """
    Represents a managed GPU Instance (GI).
    """
    uuid: str
    handle: Any
