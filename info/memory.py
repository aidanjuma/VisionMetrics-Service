import psutil


def get_ram_capacity_gib():
    # Get the total physical memory, coercing GiB.
    total_bytes = psutil.virtual_memory().total
    return int(total_bytes // (1024 ** 3))


def get_disk_capacity_gib():
    # Get the total disk capacity for root partition, coercing GiB.
    total_bytes = psutil.disk_usage('/').total
    return int(total_bytes // (1024 ** 3))
