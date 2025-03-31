from datetime import datetime

import pynvml

from models.gpu_info import GPUInfo

# Attempt to capture information about NVIDIA GPUs using NVML:
try:
    pynvml.nvmlInit()
except pynvml.NVMLError as err:
    print('Failed to initialize NVML via pynvml: ', err)


def get_gpu_usage_info(gpus: [GPUInfo]):
    # Get handle for each GPU, as found by its PCI Bus ID:
    handles = [pynvml.nvmlDeviceGetHandleByPciBusId(bus_id) for bus_id in gpus if not None]

    for handle in handles:
        # Get timestamp for when metrics were gathered:
        timestamp = datetime.now().isoformat(timespec='milliseconds')

        # Get information about current state of VRAM usage:
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_free = memory_info.free // (1024 ** 2)
        memory_used = memory_info.used // (1024 ** 2)

        # TODO: Continue gathering metrics. Back shortly, taking a break.
