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

    CREATE_GPU_STATUS_TABLE = '''
    CREATE TABLE IF NOT EXISTS gpu_status (
        gpu_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        p_state TEXT NOT NULL,
        temperature INTEGER NOT NULL,
        gpu_utilization INTEGER NOT NULL,
        memory_utilization INTEGER NOT NULL,
        clock_sm INTEGER NOT NULL,
        clock_memory INTEGER NOT NULL,
        clock_graphics INTEGER NOT NULL,
        power_usage INTEGER NOT NULL,
        memory_free_mib INTEGER NOT NULL,
        memory_used_mib INTEGER NOT NULL,
        pcie_rx INTEGER NOT NULL,
        pcie_tx INTEGER NOT NULL,
        session_id INTEGER NOT NULL,
        PRIMARY KEY (gpu_id, timestamp, session_id),
        FOREIGN KEY (gpu_id) REFERENCES gpu_info(gpu_id),
        FOREIGN KEY (session_id) REFERENCES test_session(session_id)
    );
    '''

    CREATE_TEST_SESSION_TABLE = '''
    CREATE TABLE IF NOT EXISTS test_session (
     session_id INTEGER PRIMARY KEY AUTOINCREMENT,
     is_active INTEGER NOT NULL
    );
    '''

    WRITE_GPU_STATUS_RECORD = '''
    INSERT INTO gpu_status (
    gpu_id,
    timestamp,
    p_state,
    temperature,
    gpu_utilization,
    memory_utilization,
    clock_sm,
    clock_memory,
    clock_graphics,
    power_usage,
    memory_free_mib,
    memory_used_mib,
    pcie_rx,
    pcie_tx,
    session_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    '''
