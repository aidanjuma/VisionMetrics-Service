import os
import threading
import time
from typing import Dict, List

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


class VisionMetricsServiceCLI:
    def __init__(self):
        self.console = Console()

        # Database & resource managers:
        self.db_connector = None
        self.gpu_resource_managers: Dict[str, GPUResourceManager] = {}
        self.process_manager = None
        self.system_info_cache = None
        self.latest_system_id_cache = None
        self.has_nvidia_gpu_flag = False

        # Monitoring state:
        self.monitoring_thread = None
        self.stop_monitoring_event = threading.Event()
        self.monitoring_active = False

        # Database setup:
        self.cwd = os.getcwd()
        self.database_dir = os.path.join(self.cwd, 'db')
        self.database_path = None

        if not os.path.exists(self.database_dir):
            os.makedirs(self.database_dir, exist_ok=True)
        self.database_path = os.path.join(self.database_dir, 'database.db')

    def setup_initial_resources(self) -> None:
        # Attempt to establish connection to the database:
        self.db_connector = db.DBConnector(self.database_path)
        connection = self.db_connector.connect()

        if connection is None:
            print('Connection to the database failed. Exiting...')
            exit(1)
        print('Connection to the database established successfully.')

        # Collect system information:
        self.system_info_cache = collect_system_info()
        system_info_record: tuple = (
            self.system_info_cache.ram_capacity,
            self.system_info_cache.disk_capacity,
            self.system_info_cache.total_vram_capacity
        )

        # Write system info to database & cache the latest record ID:
        self.db_connector.execute_query(
            FixedDBQuery.WRITE_SYSTEM_INFO_RECORD, system_info_record)
        self.latest_system_id_cache = int(self.db_connector.execute_query(
            FixedDBQuery.FIND_LATEST_SYSTEM_ID, fetch=True)[0][0])

        # Write CPU information to database:
        cpu_info: CPUInfo = self.system_info_cache.cpu
        cpu_info_record: tuple = (
            self.latest_system_id_cache, cpu_info.name, cpu_info.total_cores,
            cpu_info.min_frequency, cpu_info.max_frequency
        )
        self.db_connector.execute_query(
            FixedDBQuery.WRITE_CPU_INFO_RECORD, cpu_info_record)

        # Write GPU information to database:
        temp_has_nvidia_gpu = False
        for gpu in self.system_info_cache.gpus:
            gpu_info_record: tuple = (
                self.latest_system_id_cache, gpu.bus_id, gpu.name, gpu.vram_capacity_mib
            )
            self.db_connector.execute_query(
                FixedDBQuery.WRITE_GPU_INFO_RECORD, gpu_info_record)

            # Create GPUResourceManager instances for Nvidia GPUs:
            if 'nvidia' in gpu.name.lower():
                temp_has_nvidia_gpu = True
                try:
                    manager = GPUResourceManager(gpu)
                    self.gpu_resource_managers[gpu.bus_id] = manager
                    print(
                        f'Initialized GPUResourceManager for GPU: {gpu.bus_id} ({gpu.name})')
                except Exception as e:
                    print(
                        f'Failed to initialize GPUResourceManager for {gpu.bus_id}: {e}')

        self.has_nvidia_gpu_flag = temp_has_nvidia_gpu

    def _monitoring_worker(self, stop_event: threading.Event) -> None:
        session_id_result: list | None = None
        try:
            # Get the latest session ID from the database:
            if self.db_connector:
                session_id_result = self.db_connector.execute_query(
                    FixedDBQuery.FIND_ACTIVE_SESSION_ID, fetch=True)
            else:
                self.console.print(
                    '[bold red]Database connector not available in monitoring worker.[/bold red]')
                self.monitoring_active = False
                return

            if not self.system_info_cache:
                self.console.print(
                    '[bold red]System info cache lost.[/bold red]')

            # Filter for NVIDIA GPUs for monitoring:
            nvidia_gpus = [
                gpu for gpu in self.system_info_cache.gpus if 'nvidia' in gpu.name.lower()
            ]
            if not nvidia_gpus:
                self.console.print(
                    '[bold yellow]No NVIDIA GPUs available for status monitoring. Stopping monitor.[/bold yellow]')

            # Monitoring loop:
            while not stop_event.is_set():
                # Get GPU usage information:
                status_records: List[GPUStatusRecord] | None = hardware.metrics.gpu.get_gpu_usage_info(
                    nvidia_gpus)
                ram_usage_stats: tuple = hardware.metrics.memory.get_ram_usage()

                if status_records is None:
                    self.console.print(
                        '[bold yellow]No NVIDIA GPU handles could be found via NVML for status. Stopping monitor...[/bold yellow]')
                    break

                # Write the status record(s) to the database:
                for record in status_records:
                    record.session_id = int(
                        session_id_result[0][0]) if session_id_result and session_id_result[0] else None
                    gpu_id_result = self.db_connector.execute_query(
                        FixedDBQuery.FIND_GPU_ID_FROM_BUS_ID, (record.bus_id,), fetch=True)
                    if not gpu_id_result or not gpu_id_result[0]:
                        self.console.print(
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

                    self.db_connector.execute_query(
                        FixedDBQuery.WRITE_GPU_STATUS_RECORD, status_record_tuple)

                # Check if the stop event has been set before continuing:
                if stop_event.wait(1.0):
                    break
        except Exception as err:
            self.console.print(
                f'[bold red]Error during monitoring: {err}[/bold red]')
        finally:
            self.console.print(
                '[bold yellow]Monitoring worker thread finished.[/bold yellow]')
            self.monitoring_active = False

    def start_monitoring_loop(self) -> None:
        if not self.db_connector or not self.system_info_cache or not self.has_nvidia_gpu_flag:
            self.console.print(
                '[bold red]Monitoring cannot start. Initial resources not available or no NVIDIA GPU detected.[/bold red]')
            time.sleep(2)
            return

        if self.monitoring_active:
            self.console.print(
                '[yellow]Monitoring is already active.[/yellow]')
            time.sleep(1)
            return

        self.console.print(
            '[bold green]Starting metrics collection in background...[/bold green]')
        self.stop_monitoring_event.clear()
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_worker, args=(self.stop_monitoring_event,), daemon=True)
        self.monitoring_active = True
        self.monitoring_thread.start()
        time.sleep(1)

    def stop_monitoring_loop(self) -> None:
        if not self.monitoring_active or self.monitoring_thread is None:
            self.console.print(
                '[yellow]Monitoring is not currently active.[/yellow]')
            time.sleep(1)
            return

        self.console.print(
            '[bold yellow]Attempting to stop monitoring...[/bold yellow]')
        self.stop_monitoring_event.set()
        self.monitoring_thread.join(timeout=5.0)

        if self.monitoring_thread.is_alive():
            self.console.print(
                '[bold red]Monitoring thread did not stop within timeout.[/bold red]')
            self.monitoring_active = False
        else:
            self.console.print(
                '[bold green]Monitoring stopped successfully.[/bold green]')
            self.monitoring_active = False

        self.monitoring_thread = None
        time.sleep(1)

    def display_system_info(self) -> None:
        if not self.system_info_cache:
            self.console.print(
                '[bold red]System information cache not available.[/bold red]')
            return

        # CPU Info
        cpu_panel = Panel(
            f'[bold]Name:[/bold] {self.system_info_cache.cpu.name} '
            f'[bold]Cores:[/bold] {self.system_info_cache.cpu.total_cores} '
            f'[bold]Frequency:[/bold] {self.system_info_cache.cpu.min_frequency}-{self.system_info_cache.cpu.max_frequency} MHz',
            title='[bold blue]CPU Info[/bold blue]',
            expand=False
        )

        # RAM Info
        ram_panel = Panel(
            f'[bold]Total Capacity:[/bold] {self.system_info_cache.ram_capacity} GB',
            title='[bold green]RAM Info[/bold green]',
            expand=False
        )

        # GPU Info
        gpu_table = Table(
            title='[bold magenta]GPU(s) Info[/bold magenta]',
            show_header=True,
            header_style='bold magenta'
        )
        gpu_table.add_column('Bus ID', style='dim', width=15)
        gpu_table.add_column('Name', width=30)
        gpu_table.add_column('VRAM (MiB)', justify='right')

        total_vram = 0
        for gpu in self.system_info_cache.gpus:
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

        self.console.print(cpu_panel)
        self.console.print(ram_panel)
        self.console.print(gpu_table)
        self.console.print(vram_panel)

    def display_monitoring_data(self) -> None:
        if not self.db_connector:
            self.console.print(
                '[bold red]Database connector not available.[/bold red]')
            time.sleep(2)
            return

        page_number = 1
        page_size = 10

        while True:
            # Get total record count:
            count_result = self.db_connector.execute_query(
                FixedDBQuery.COUNT_GPU_STATUS_RECORDS, fetch=True)
            total_records = count_result[0][0] if count_result and count_result[0] else 0
            if total_records == 0:
                self.console.clear()
                self.console.print(
                    '[yellow]No monitoring data found.[/yellow]')
                self.console.print('Press Enter to return to the menu.')
                input()
                return

            # Display current page position out of page count:
            total_pages = (total_records + page_size - 1) // page_size
            page_number = max(1, min(page_number, total_pages))

            # Calculate offset and fetch data for the current page:
            offset = (page_number - 1) * page_size
            data = self.db_connector.execute_query(
                FixedDBQuery.FETCH_GPU_STATUS_PAGE, (page_size, offset), fetch=True)

            # Prepare table for display:
            table = Table(
                title=f'GPU Monitoring Data - Page {page_number}/{total_pages}',
                show_header=True,
                header_style='bold cyan'
            )
            table.add_column('Timestamp', style='dim', width=26)
            table.add_column('GPU Name')
            table.add_column('Temp (°C)', justify='right')
            table.add_column('GPU Util (%)', justify='right')
            table.add_column('Mem Util (%)', justify='right')
            table.add_column('Power (W)', justify='right')
            table.add_column('VRAM Used (MiB)', justify='right')
            table.add_column('RAM Used (MiB)', justify='right')

            if not data:
                self.console.print(
                    '[yellow]No data found for this page.[/yellow]')
                self.console.print('Press Enter to return to the menu.')
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

            self.console.clear()
            self.console.print(table)
            self.console.print(f'Page {page_number}/{total_pages}')

            # Prompt for user interaction:
            self.console.print(
                'Press \'[\' for previous, \']\' for next page, or \'q\' to return to menu...')

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

    def display_menu(self) -> str:
        self.console.print('\n[bold underline]Main Menu[/bold underline]')

        status_text = '[green]Active[/green]' if self.monitoring_active else '[yellow]Inactive[/yellow]'
        self.console.print(f'Monitoring Status: {status_text}')

        # Define options:
        options = {
            '1': 'Stop Monitoring' if self.monitoring_active else 'Start Monitoring',
            '2': 'View Monitoring Data',
            '3': 'Exit'
        }
        choices = list(options.keys())

        # Display options:
        for key, value in options.items():
            self.console.print(f'{key}. {value}')

        # Prompt for user input:
        choice = Prompt.ask('Choose an option', choices=choices, default='3')
        match choice:
            case '1':
                return 'stop' if self.monitoring_active else 'start'
            case '2':
                return 'view_monitoring_data'
            case '3':
                return 'exit'
            case _:
                return 'exit'

    def display_mig_profile_manager(self) -> None:
        self.console.print(
            '\n[bold underline]MIG Profile Manager[/bold underline]')

        # Define options:
        options = {
            '1': 'Create MIG Profile',
            '2': 'Delete MIG Profile',
            '3': 'List MIG Profiles',
            '4': 'Return to Main Menu'
        }

        # TODO: Implement MIG profile manager functionality.

    def run(self):
        try:
            self.setup_initial_resources()
            if self.db_connector is None:
                self.console.print(
                    '[bold red]Database connection failed during setup. Exiting.[/bold red]')
                return
            if self.system_info_cache is None:
                self.console.print(
                    '[bold red]System info collection failed during setup. Exiting.[/bold red]')
                return
        except Exception as e:
            self.console.print(
                f'[bold red]An error occurred during initial setup: {e}[/bold red]')
            return

        while True:
            self.console.clear()
            self.display_system_info()
            choice = self.display_menu()

            match choice:
                case 'start':
                    self.start_monitoring_loop()
                case 'stop':
                    self.stop_monitoring_loop()
                case 'view_monitoring_data':
                    self.display_monitoring_data()
                case 'mig_profile_manager':
                    self.display_mig_profile_manager()
                case 'exit':
                    self.console.print(
                        '[bold cyan]Exiting application.[/bold cyan]')
                    if self.monitoring_active:
                        self.stop_monitoring_loop()
                    break
