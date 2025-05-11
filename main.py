import os
import time
from typing import List, Dict

import db.connector as db
import hardware.metrics.gpu
import hardware.metrics.memory
from enums.queries import FixedDBQuery
from hardware.info import collect_system_info
from models.cpu_info import CPUInfo
from models.gpu_info import GPUInfo
from models.gpu_status_record import GPUStatusRecord
from models.system_info import SystemInfo
from hardware.managers.gpu_resource_manager import GPUResourceManager
from hardware.managers.process_manager import ProcessManager

# -= Constants =-
DB_CONNECTOR: db.DBConnector | None = None
GPU_RESOURCE_MANAGERS: Dict[str, GPUResourceManager] = {}
PROCESS_MANAGER: ProcessManager | None = None
SYSTEM_INFO_CACHE: SystemInfo | None = None
LATEST_SYSTEM_ID_CACHE: int | None = None
HAS_NVIDIA_GPU_FLAG: bool = False

# -= Directory & Database Setup =-
CWD: str = os.getcwd()
DATABASE_DIR = os.path.join(CWD, 'db')
DATABASE_PATH = None

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_PATH = os.path.join(DATABASE_DIR, 'database.db')


def setup_initial_resources() -> None:
    global DB_CONNECTOR, GPU_RESOURCE_MANAGERS, PROCESS_MANAGER
    global SYSTEM_INFO_CACHE, LATEST_SYSTEM_ID_CACHE, HAS_NVIDIA_GPU_FLAG

    # Attempt to establish connection to the database.
    DB_CONNECTOR = db.DBConnector(DATABASE_PATH)
    connection = DB_CONNECTOR.connect()

    if connection is None:
        print('Connection to the database failed. Exiting...')
        exit(1)
    print('Connection to the database established successfully.')

    # Collect system information, i.e. CPU, GPU(s), RAM, disk, and total VRAM capacity.
    SYSTEM_INFO_CACHE: SystemInfo = collect_system_info()
    system_info_record: tuple = (SYSTEM_INFO_CACHE.ram_capacity,
                                 SYSTEM_INFO_CACHE.disk_capacity,
                                 SYSTEM_INFO_CACHE.total_vram_capacity)

    # Write RAM, disk, and total VRAM capacity to database & cache the latest record ID.
    DB_CONNECTOR.execute_query(
        FixedDBQuery.WRITE_SYSTEM_INFO_RECORD, system_info_record)
    LATEST_SYSTEM_ID_CACHE = int(DB_CONNECTOR.execute_query(
        FixedDBQuery.FIND_LATEST_SYSTEM_ID, fetch=True)[0][0])

    # Write CPU information to database.
    cpu_info: CPUInfo = SYSTEM_INFO_CACHE.cpu
    cpu_info_record: tuple = (
        LATEST_SYSTEM_ID_CACHE, cpu_info.name, cpu_info.total_cores,
        cpu_info.min_frequency, cpu_info.max_frequency)
    DB_CONNECTOR.execute_query(
        FixedDBQuery.WRITE_CPU_INFO_RECORD, cpu_info_record)

    # Write GPU information to database.
    temp_has_nvidia_gpu = False
    for gpu in SYSTEM_INFO_CACHE.gpus:
        gpu_info_record: tuple = (
            LATEST_SYSTEM_ID_CACHE, gpu.bus_id, gpu.name, gpu.vram_capacity_mib)
        DB_CONNECTOR.execute_query(
            FixedDBQuery.WRITE_GPU_INFO_RECORD, gpu_info_record)

        # Create GPUResourceManager instances for Nvidia GPUs:
        if 'nvidia' in gpu.name.lower():
            temp_has_nvidia_gpu = True
            try:
                manager = GPUResourceManager(gpu)
                GPU_RESOURCE_MANAGERS[gpu.bus_id] = manager
                print(
                    f'Initialized GPUResourceManager for GPU: {gpu.bus_id} ({gpu.name})')
            except Exception as e:
                print(
                    f'Failed to initialize GPUResourceManager for {gpu.bus_id}: {e}')
    HAS_NVIDIA_GPU_FLAG = temp_has_nvidia_gpu


def start_monitoring_loop() -> None:
    if not DB_CONNECTOR or not SYSTEM_INFO_CACHE or not HAS_NVIDIA_GPU_FLAG:
        print('Monitoring cannot start. Initial resources not available or no NVIDIA GPU detected for monitoring.')
        return

    print('Starting metrics collection loop (Ctrl+C to stop)...')
    try:
        # Get the latest session ID from the database:
        session_id_result: list | None = DB_CONNECTOR.execute_query(
            FixedDBQuery.FIND_ACTIVE_SESSION_ID, fetch=True)

        while True:
            # Filter for NVIDIA GPUs for monitoring, as get_gpu_usage_info() expects NVML-compatible GPUs:
            nvidia_gpus = [
                gpu for gpu in SYSTEM_INFO_CACHE.gpus if 'nvidia' in gpu.name.lower()]
            if not nvidia_gpus:
                print(
                    'No NVIDIA GPUs available for status monitoring. Stopping monitor.')
                break

            # Get GPU usage information for each NVIDIA GPU:
            status_records: List[GPUStatusRecord] | None = hardware.metrics.gpu.get_gpu_usage_info(
                nvidia_gpus)
            ram_usage_stats: tuple = hardware.metrics.memory.get_ram_usage()

            # If no status records could be found, stop monitoring.
            if status_records is None:
                print(
                    'No NVIDIA GPU handles could be found via NVML for status. Stopping monitor...')
                break

            # Write the status record(s) to the database:
            for record in status_records:
                record.session_id = int(
                    session_id_result[0][0]) if session_id_result else None
                gpu_id_result = DB_CONNECTOR.execute_query(FixedDBQuery.FIND_GPU_ID_FROM_BUS_ID,
                                                           (record.bus_id,), fetch=True)
                if not gpu_id_result or not gpu_id_result[0]:
                    print(
                        f'Warning: Could not find GPU ID for bus ID {record.bus_id}. Skipping record...')
                    continue
                gpu_id = gpu_id_result[0][0]

                # Structure the status record for database insertion:
                status_record_tuple = (
                    gpu_id, record.timestamp, record.p_state, record.temperature, record.gpu_utilization,
                    record.memory_utilization, record.clock_sm, record.clock_memory, record.clock_graphics,
                    record.power_usage, record.memory_free_mib, record.memory_used_mib, record.pcie_rx, record.pcie_tx,
                    # ram_usage_stats[1] is total_gb, ram_usage_stats[0] is used_gb
                    record.session_id, ram_usage_stats[0], ram_usage_stats[1])

                DB_CONNECTOR.execute_query(
                    FixedDBQuery.WRITE_GPU_STATUS_RECORD, status_record_tuple)

            # Repeat roughly every second.
            time.sleep(1)
    except KeyboardInterrupt:
        print('Log collection stopped by user.')
    finally:
        print('Monitoring loop ended.')


def main():
    pass


if __name__ == '__main__':
    main()
