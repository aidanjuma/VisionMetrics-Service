import cpuinfo
import psutil

from models.cpu_info import CPUInfo


def get_cpu_name() -> str:
    info = cpuinfo.get_cpu_info()
    return info.get('brand_raw', 'Unknown')


def get_cpu_details() -> CPUInfo:
    physical_cores = psutil.cpu_count(logical=False)
    total_cores = psutil.cpu_count(logical=True)
    frequency = psutil.cpu_freq()
    min_frequency = frequency.min if frequency else 0.0
    max_frequency = frequency.max if frequency else 0.0

    return CPUInfo(
        name=get_cpu_name(),
        physical_cores=physical_cores,
        total_cores=total_cores,
        min_frequency=min_frequency,
        max_frequency=max_frequency
    )
