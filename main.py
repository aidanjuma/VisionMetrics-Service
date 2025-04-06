import os
import time
from sqlite3 import Connection

import db.connector as db
import metrics.gpu
from enums.queries import FixedDBQuery
from info.collection import collect_system_info
from models.cpu_info import CPUInfo
from models.gpu_info import GPUInfo
from models.gpu_status_record import GPUStatusRecord
from models.system_info import SystemInfo

# Get CWD & data directory:
cwd: str = os.getcwd()
data_dir = os.path.join(cwd, 'data')
database_path = None

# Ensure the data directory exists before starting service:
if not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)

database_path = os.path.join(data_dir, 'database.db')

if __name__ == '__main__':
    # Attempt to connect to the database, creating it if it doesn't already exist.
    connector = db.DBConnector(database_path)
    connection: Connection | None = connector.connect()

    if connection is None:
        print('Connection to the database failed. Exiting...')
        exit(1)
    print('Connection to the database established successfully.')

    # Collect static system information:
    system_info: SystemInfo = collect_system_info()
    system_info_record = (system_info.ram_capacity, system_info.disk_capacity, system_info.total_vram_capacity)

    # Write memory-relayed information to disk:
    connector.execute_query(FixedDBQuery.WRITE_SYSTEM_INFO_RECORD, system_info_record)
    latest_system_id: int = int(connector.execute_query(FixedDBQuery.FIND_LATEST_SYSTEM_ID, fetch=True)[0][0])

    # Write CPU-related information to disk:
    cpu_info: CPUInfo = system_info.cpu
    cpu_info_record: tuple = (
        latest_system_id, cpu_info.name, cpu_info.total_cores, cpu_info.min_frequency, cpu_info.max_frequency)
    connector.execute_query(FixedDBQuery.WRITE_CPU_INFO_RECORD, cpu_info_record)

    # Write GPU-related information to disk:
    has_nvidia_gpu = False
    gpus: [GPUInfo] = system_info.gpus
    for gpu in gpus:
        gpu_info_record: tuple = (latest_system_id, gpu.bus_id, gpu.name, gpu.vram_capacity_mib)
        connector.execute_query(FixedDBQuery.WRITE_GPU_INFO_RECORD, gpu_info_record)

        # Flag to indicate if there is an Nvidia GPU present, and thus NVML:
        if 'nvidia' in gpu.name.lower():
            has_nvidia_gpu = True

    if not has_nvidia_gpu:
        print('No NVIDIA GPU found, so cannot continue taking measurements. Exiting...')
        exit(1)

    try:
        while True:
            status_records: [GPUStatusRecord] = metrics.gpu.get_gpu_usage_info(gpus)

            if status_records is None:
                print('No NVIDIA GPU handles could be found via NVML. Exiting...')
                exit(1)

            # Write GPUStatusRecord information to DB:
            for record in status_records:
                gpu_id = connector.execute_query(FixedDBQuery.FIND_GPU_ID_FROM_BUS_ID, record.bus_id)
                status_record = (
                    gpu_id, record.timestamp, record.p_state, record.temperature, record.gpu_utilization,
                    record.memory_utilization, record.clock_sm, record.clock_memory, record.clock_graphics,
                    record.power_usage, record.memory_free_mib, record.memory_used_mib, record.pcie_rx, record.pcie_tx,
                    record.session_id)

                connector.execute_query(FixedDBQuery.WRITE_GPU_STATUS_RECORD, status_record)

            # ...repeat the process every second.
            time.sleep(1)
    except KeyboardInterrupt:
        print('Log collection stopped by user.')
    finally:
        connector.disconnect()
