import enum


class FixedDBQuery(enum.Enum):
    CREATE_CPU_INFO_TABLE = '''
        CREATE TABLE IF NOT EXISTS cpu_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            cores INTEGER NOT NULL,
            frequency REAL NOT NULL,
            FOREIGN KEY (system_id) REFERENCES system_info(system_id)
        );
        '''

    CREATE_GPU_INFO_TABLE = '''
        CREATE TABLE IF NOT EXISTS gpu_info (
            gpu_id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id INTEGER NOT NULL,
            bus_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vram_capacity INTEGER NOT NULL,
            FOREIGN KEY (system_id) REFERENCES system_infp(system_id)
        );
        '''

    CREATE_SYSTEM_INFO_TABLE = '''
        CREATE TABLE IF NOT EXISTS system_info (
            system_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ram_capacity INTEGER NOT NULL,
            disk_capacity INTEGER NOT NULL,
            total_vram_capacity INTEGER NOT NULL 
        );
        '''

    # TODO: More queries...
