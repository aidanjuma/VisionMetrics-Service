import psutil


def get_ram_usage() -> tuple:
    # Get memory (RAM) statistics:
    memory = psutil.virtual_memory()

    # Convert bytes to MiB:
    used_ram_mib = memory.used // (1024 ** 2)
    percent_used = memory.percent

    return (int(used_ram_mib), int(percent_used))
