from datetime import datetime

import pynvml

from models.gpu_info import GPUInfo
from models.gpu_status_record import GPUStatusRecord

# Attempt to capture information about NVIDIA GPUs using NVML:
try:
    pynvml.nvmlInit()
except pynvml.NVMLError as err:
    print('Failed to initialize NVML via pynvml: ', err)


def get_gpu_usage_info(gpus: [GPUInfo]) -> [GPUStatusRecord]:
    # Get handle for each GPU, as found by its PCI Bus ID:
    handles = {bus_id: pynvml.nvmlDeviceGetHandleByPciBusId(bus_id) for bus_id in gpus if bus_id is not None}

    data = {}
    for bus_id, handle in handles.items():
        # Get timestamp for when metrics were gathered:
        timestamp = datetime.now().isoformat(timespec='milliseconds')

        # Get current power-state for the GPU:
        p_state = pynvml.nvmlDeviceGetPowerState(handle)

        # Get current core temperature:
        temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        # Get current utilization rates for cores & memory:
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_utilization = utilization.gpu
        memory_utilization = utilization.memory

        # Get clock information across components:
        clock_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
        clock_memory = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
        clock_graphics = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)

        # Get power usage, presented in watts (W):
        power_usage = pynvml.nvmlDeviceGetPowerUsage(handle)

        # Get information about current state of VRAM usage:
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_free = memory_info.free // (1024 ** 2)
        memory_used = memory_info.used // (1024 ** 2)

        # PCIE-throughput counters in KB/s:
        pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES)
        pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES)

        gpu: GPUInfo = next(filter(lambda gpu: gpu.bus_id == bus_id, gpus), None)
        data[bus_id] = GPUStatusRecord(name=gpu.name, bus_id=gpu.bus_id, vram_capacity_mib=gpu.vram_capacity_mib,
                                       timestamp=timestamp, p_state=p_state, temperature=temperature,
                                       gpu_utilization=gpu_utilization, memory_utilization=memory_utilization,
                                       clock_sm=clock_sm, clock_memory=clock_memory, clock_graphics=clock_graphics,
                                       power_usage=power_usage, memory_free_mib=memory_free,
                                       memory_used_mib=memory_used, pcie_rx=pcie_rx, pcie_tx=pcie_tx)

    return data.values()
