from datetime import datetime

import pynvml

from models.gpu_info import GPUInfo
from models.gpu_status_record import GPUStatusRecord

# Attempt to initialize NVML:
try:
    pynvml.nvmlInit()
except pynvml.NVMLError as err:
    print('Failed to initialize NVML via pynvml: ', err)


def get_gpu_usage_info(gpus: [GPUInfo]) -> list[GPUStatusRecord] | None:
    # Create a list to store GPUStatusRecord objects
    records = []

    for gpu in gpus:
        # Try getting the handle for each GPU using its PCI Bus ID:
        try:
            handle = pynvml.nvmlDeviceGetHandleByPciBusId(gpu.bus_id)
        except pynvml.NVMLError as err:
            print(f"Failed to get handle for GPU with bus_id {gpu.bus_id}: ", err)
            continue  # Skip GPU if error occurs

        # Get timestamp when metrics were gathered:
        timestamp = datetime.now().isoformat(timespec='milliseconds')

        # Get current power-state for the GPU:
        p_state = pynvml.nvmlDeviceGetPowerState(handle)

        # Get current GPU core temperature:
        temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        # Get current core & memory utilization %s:
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_utilization = utilization.gpu
        memory_utilization = utilization.memory

        # Get current clock information for SM, memory & core:
        clock_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
        clock_memory = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
        clock_graphics = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)

        # Get power usage (in Watts, W):
        power_usage = pynvml.nvmlDeviceGetPowerUsage(handle)

        # Get memory usage information:
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_free = memory_info.free // (1024 ** 2)
        memory_used = memory_info.used // (1024 ** 2)

        # Get PCIE throughput information:
        pcie_rx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES)
        pcie_tx = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES)

        record = GPUStatusRecord(
            name=gpu.name,
            bus_id=gpu.bus_id,
            vram_capacity_mib=gpu.vram_capacity_mib,
            timestamp=timestamp,
            p_state=p_state,
            temperature=temperature,
            gpu_utilization=gpu_utilization,
            memory_utilization=memory_utilization,
            clock_sm=clock_sm,
            clock_memory=clock_memory,
            clock_graphics=clock_graphics,
            power_usage=power_usage,
            memory_free_mib=memory_free,
            memory_used_mib=memory_used,
            pcie_rx=pcie_rx,
            pcie_tx=pcie_tx
        )

        records.append(record)

    # Return the collection of GPUStatusRecord objects:
    return records if records else None
