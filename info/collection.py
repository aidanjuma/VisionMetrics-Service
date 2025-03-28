from info.cpu import get_cpu_info
from info.gpu import get_gpu_info
from info.memory import get_ram_capacity_gib, get_disk_capacity_gib
from models.cpu_info import CPUInfo
from models.gpu_info import GPUInfo
from models.system_info import SystemInfo


def collect_system_info() -> SystemInfo:
    cpu_info: CPUInfo = get_cpu_info()
    gpus: GPUInfo = get_gpu_info()
    ram_capacity: int = get_ram_capacity_gib()
    disk_capacity: int = get_disk_capacity_gib()

    return SystemInfo(cpu_info, gpus, ram_capacity, disk_capacity)
