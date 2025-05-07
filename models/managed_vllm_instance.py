from dataclasses import dataclass
import subprocess
from typing import List


@dataclass
class ManagedVllmInstance:
    """
    Represents a managed vLLM instance process.
    """
    port: int
    process: subprocess.Popen
    mig_uuid: str
    model_name_or_path: str
    command: List[str]
