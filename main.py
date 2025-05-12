import os
import threading
import time
from typing import List, Dict

import readchar
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

import db.connector as db
import hardware.metrics.gpu
import hardware.metrics.memory
from enums.queries import FixedDBQuery
from hardware.info.collection import collect_system_info
from hardware.managers.gpu_resource_manager import GPUResourceManager
from hardware.managers.process_manager import ProcessManager
from models.cpu_info import CPUInfo
from models.gpu_status_record import GPUStatusRecord
from models.system_info import SystemInfo

CONSOLE = Console()

# -= Globals =-
DB_CONNECTOR: db.DBConnector | None = None
GPU_RESOURCE_MANAGERS: Dict[str, GPUResourceManager] = {}
PROCESS_MANAGER: ProcessManager | None = None
SYSTEM_INFO_CACHE: SystemInfo | None = None
LATEST_SYSTEM_ID_CACHE: int | None = None
HAS_NVIDIA_GPU_FLAG: bool = False

# -= Monitoring State =-
MONITORING_THREAD: threading.Thread | None = None
STOP_MONITORING_EVENT = threading.Event()
MONITORING_ACTIVE = False

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
    SYSTEM_INFO_CACHE = collect_system_info()
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


def __monitoring_worker(stop_event: threading.Event) -> None:
    global MONITORING_ACTIVE

    session_id_result: list | None = None
    try:
        # Get the latest session ID from the database:
        if DB_CONNECTOR:
            session_id_result = DB_CONNECTOR.execute_query(
                FixedDBQuery.FIND_ACTIVE_SESSION_ID, fetch=True)
        else:
            CONSOLE.print(
                '[bold red]Database connector not available in monitoring worker.[/bold red]')
            MONITORING_ACTIVE = False
            return

        if not SYSTEM_INFO_CACHE:
            CONSOLE.print('[bold red]System info cache lost.[/bold red]')

        # Filter for NVIDIA GPUs for monitoring:
        nvidia_gpus = [
            gpu for gpu in SYSTEM_INFO_CACHE.gpus if 'nvidia' in gpu.name.lower()]
        if not nvidia_gpus:
            CONSOLE.print(
                '[bold yellow]No NVIDIA GPUs available for status monitoring. Stopping monitor.[/bold yellow]')

        # Here is the actual monitoring logic:
        while not stop_event.is_set():
            # Get GPU usage information:
            status_records: List[GPUStatusRecord] | None = hardware.metrics.gpu.get_gpu_usage_info(
                nvidia_gpus)
            ram_usage_stats: tuple = hardware.metrics.memory.get_ram_usage()

            if status_records is None:
                CONSOLE.print(
                    '[bold yellow]No NVIDIA GPU handles could be found via NVML for status. Stopping monitor...[/bold yellow]')
                break

            # Write the status record(s) to the database:
            for record in status_records:
                record.session_id = int(
                    session_id_result[0][0]) if session_id_result and session_id_result[0] else None
                gpu_id_result = DB_CONNECTOR.execute_query(FixedDBQuery.FIND_GPU_ID_FROM_BUS_ID,
                                                           (record.bus_id,), fetch=True)
                if not gpu_id_result or not gpu_id_result[0]:
                    CONSOLE.print(
                        f'[yellow]Warning: Could not find GPU ID for bus ID {record.bus_id}. Skipping record...[/yellow]')
                    continue
                gpu_id = gpu_id_result[0][0]

                status_record_tuple = (
                    gpu_id,                       # 1. gpu_id
                    record.timestamp,             # 2. timestamp
                    record.p_state,               # 3. p_state
                    record.temperature,           # 4. temperature
                    record.gpu_utilization,       # 5. gpu_utilization
                    record.memory_utilization,    # 6. memory_utilization
                    record.clock_sm,              # 7. clock_sm
                    record.clock_memory,          # 8. clock_memory
                    record.clock_graphics,        # 9. clock_graphics
                    record.power_usage,           # 10. power_usage
                    record.memory_free_mib,       # 11. memory_free_mib
                    record.memory_used_mib,       # 12. memory_used_mib
                    record.pcie_rx,               # 13. pcie_rx
                    record.pcie_tx,               # 14. pcie_tx
                    record.session_id,            # 15. session_id
                    ram_usage_stats[0],           # 16. system_ram_used_mib
                    # 17. system_ram_used_percentage
                    ram_usage_stats[1]
                )

                DB_CONNECTOR.execute_query(
                    FixedDBQuery.WRITE_GPU_STATUS_RECORD, status_record_tuple)

            # Check if the stop event has been set, before continuing the loop after 1 second:
            if stop_event.wait(1.0):
                break
    except Exception as err:
        CONSOLE.print(f'[bold red]Error during monitoring: {err}[/bold red]')
    finally:
        CONSOLE.print(
            '[bold yellow]Monitoring worker thread finished.[/bold yellow]')
        MONITORING_ACTIVE = False


def start_monitoring_loop() -> None:
    global MONITORING_THREAD, MONITORING_ACTIVE, STOP_MONITORING_EVENT

    if not DB_CONNECTOR or not SYSTEM_INFO_CACHE or not HAS_NVIDIA_GPU_FLAG:
        CONSOLE.print(
            '[bold red]Monitoring cannot start. Initial resources not available or no NVIDIA GPU detected.[/bold red]')
        time.sleep(2)
        return

    if MONITORING_ACTIVE:
        CONSOLE.print('[yellow]Monitoring is already active.[/yellow]')
        time.sleep(1)
        return

    CONSOLE.print(
        '[bold green]Starting metrics collection in background...[/bold green]')
    STOP_MONITORING_EVENT.clear()
    MONITORING_THREAD = threading.Thread(
        target=__monitoring_worker, args=(STOP_MONITORING_EVENT,), daemon=True)
    MONITORING_ACTIVE = True
    MONITORING_THREAD.start()
    time.sleep(1)


def stop_monitoring_loop() -> None:
    global MONITORING_THREAD, MONITORING_ACTIVE, STOP_MONITORING_EVENT

    if not MONITORING_ACTIVE or MONITORING_THREAD is None:
        CONSOLE.print('[yellow]Monitoring is not currently active.[/yellow]')
        time.sleep(1)
        return

    CONSOLE.print(
        '[bold yellow]Attempting to stop monitoring...[/bold yellow]')
    STOP_MONITORING_EVENT.set()
    MONITORING_THREAD.join(timeout=5.0)

    if MONITORING_THREAD.is_alive():
        CONSOLE.print(
            '[bold red]Monitoring thread did not stop within timeout.[/bold red]')
        MONITORING_ACTIVE = False
    else:
        CONSOLE.print(
            '[bold green]Monitoring stopped successfully.[/bold green]')
        MONITORING_ACTIVE = False

    MONITORING_THREAD = None
    time.sleep(1)


def display_system_info() -> None:
    if not SYSTEM_INFO_CACHE:
        CONSOLE.print(
            '[bold red]System information cache not available.[/bold red]')
        return

    # -= CPU Info =-
    cpu_panel = Panel(
        f'[bold]Name:[/bold] {SYSTEM_INFO_CACHE.cpu.name} '
        f'[bold]Cores:[/bold] {SYSTEM_INFO_CACHE.cpu.total_cores} '
        f'[bold]Frequency:[/bold] {SYSTEM_INFO_CACHE.cpu.min_frequency}-{SYSTEM_INFO_CACHE.cpu.max_frequency} MHz',
        title='[bold blue]CPU Info[/bold blue]',
        expand=False
    )

    # -= RAM Info =-
    ram_panel = Panel(
        f'[bold]Total Capacity:[/bold] {SYSTEM_INFO_CACHE.ram_capacity} GB',
        title='[bold green]RAM Info[/bold green]',
        expand=False
    )

    # -= GPU Info =-
    gpu_table = Table(title='[bold magenta]GPU(s) Info[/bold magenta]',
                      show_header=True, header_style='bold magenta')
    gpu_table.add_column('Bus ID', style='dim', width=15)
    gpu_table.add_column('Name', width=30)
    gpu_table.add_column('VRAM (MiB)', justify='right')

    total_vram = 0
    for gpu in SYSTEM_INFO_CACHE.gpus:
        gpu_table.add_row(
            gpu.bus_id,
            gpu.name,
            str(gpu.vram_capacity_mib)
        )
        total_vram += gpu.vram_capacity_mib

    vram_panel = Panel(
        f'[bold]Total VRAM:[/bold] {total_vram} MiB',
        title='[bold cyan]Total VRAM[/bold cyan]',
        expand=False
    )

    CONSOLE.print(cpu_panel)
    CONSOLE.print(ram_panel)
    CONSOLE.print(gpu_table)
    CONSOLE.print(vram_panel)


def display_monitoring_data() -> None:
    if not DB_CONNECTOR:
        CONSOLE.print('[bold red]Database connector not available.[/bold red]')
        time.sleep(2)
        return

    page_number = 1
    page_size = 10

    while True:
        # Get total record count:
        count_result = DB_CONNECTOR.execute_query(
            FixedDBQuery.COUNT_GPU_STATUS_RECORDS, fetch=True)
        total_records = count_result[0][0] if count_result and count_result[0] else 0
        if total_records == 0:
            CONSOLE.clear()
            CONSOLE.print('[yellow]No monitoring data found.[/yellow]')
            CONSOLE.print('Press Enter to return to the menu.')
            input()
            return

        # Display current page position out of page count:
        total_pages = (total_records + page_size - 1) // page_size
        page_number = max(1, min(page_number, total_pages))

        # Calculate offset and fetch data for the current page:
        offset = (page_number - 1) * page_size
        data = DB_CONNECTOR.execute_query(
            FixedDBQuery.FETCH_GPU_STATUS_PAGE, (page_size, offset), fetch=True)

        # Prepare table for display:
        table = Table(title=f'GPU Monitoring Data - Page {page_number}/{total_pages}',
                      show_header=True, header_style='bold cyan')
        table.add_column('Timestamp', style='dim', width=26)
        table.add_column('GPU Name')
        table.add_column('Temp (°C)', justify='right')
        table.add_column('GPU Util (%)', justify='right')
        table.add_column('Mem Util (%)', justify='right')
        table.add_column('Power (W)', justify='right')
        table.add_column('VRAM Used (MiB)', justify='right')
        table.add_column('RAM Used (MiB)', justify='right')

        if not data:
            CONSOLE.print('[yellow]No data found for this page.[/yellow]')
            CONSOLE.print('Press Enter to return to the menu.')
            input()
            return

        for row in data:
            # Perform formatting on timestamp (readability):
            timestamp = row[0].replace('T', ' ')
            if '.' in timestamp:
                timestamp = timestamp.split('.')[0]

            table.add_row(
                timestamp,
                str(row[1]),  # GPU Name
                str(row[2]),  # Temp
                str(row[3]),  # GPU Util
                str(row[4]),  # Mem Util
                str(row[5]),  # Power
                str(row[6]),  # VRAM Used
                str(row[7])   # RAM Used
            )

        CONSOLE.clear()
        CONSOLE.print(table)
        CONSOLE.print(f"Page {page_number}/{total_pages}")

        # Prompt for user interaction:
        CONSOLE.print(
            "Press '[' for previous, ']' for next page, or 'q' to return to menu...")

        # Perform action if requested:
        try:
            action = readchar.readkey()
        except KeyboardInterrupt:
            action = 'q'

        match action:
            case '[':
                if page_number > 1:
                    page_number -= 1
            case ']':
                if page_number < total_pages:
                    page_number += 1
            case 'q':
                break


def display_menu() -> str:
    CONSOLE.print('\n[bold underline]Main Menu[/bold underline]')

    status_text = '[green]Active[/green]' if MONITORING_ACTIVE else '[yellow]Inactive[/yellow]'
    CONSOLE.print(f'Monitoring Status: {status_text}')

    # Define options:
    options = {
        '1': 'Stop Monitoring' if MONITORING_ACTIVE else 'Start Monitoring',
        '2': 'View Monitoring Data',
        '3': 'Exit'
    }
    choices = list(options.keys())

    # Display options:
    for key, value in options.items():
        CONSOLE.print(f'{key}. {value}')

    # Prompt for user input:
    choice = Prompt.ask('Choose an option', choices=choices, default='3')
    match choice:
        case '1':
            return 'stop' if MONITORING_ACTIVE else 'start'
        case '2':
            return 'view_monitoring_data'
        case '3':
            return 'exit'
        case _:
            return 'exit'


def cli():
    try:
        setup_initial_resources()
        if DB_CONNECTOR is None:
            CONSOLE.print(
                '[bold red]Database connection failed during setup. Exiting.[/bold red]')
            return
        if SYSTEM_INFO_CACHE is None:
            CONSOLE.print(
                '[bold red]System info collection failed during setup. Exiting.[/bold red]')
            return
    except Exception as e:
        CONSOLE.print(
            f'[bold red]An error occurred during initial setup: {e}[/bold red]')
        return

    while True:
        CONSOLE.clear()
        display_system_info()
        choice = display_menu()

        match choice:
            case 'start':
                start_monitoring_loop()
            case 'stop':
                stop_monitoring_loop()
            case 'view_monitoring_data':
                display_monitoring_data()
            case 'exit':
                CONSOLE.print('[bold cyan]Exiting application.[/bold cyan]')
                if MONITORING_ACTIVE:
                    stop_monitoring_loop()
                break


def main():
    cli()


if __name__ == '__main__':
    main()
