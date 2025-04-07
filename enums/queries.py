import enum


class FixedDBQuery(enum.Enum):
    # -=- Table Creation -=-
    CREATE_CPU_INFO_TABLE = '''
    CREATE TABLE IF NOT EXISTS cpu_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        system_id INTEGER NOT NULL,
        model_name TEXT NOT NULL,
        cores INTEGER NOT NULL,
        min_frequency REAL NOT NULL,
        max_frequency REAL NOT NULL,
        FOREIGN KEY (system_id) REFERENCES system_info(system_id)
    );
    '''

    CREATE_GPU_INFO_TABLE = '''
    CREATE TABLE IF NOT EXISTS gpu_info (
        gpu_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_id TEXT UNIQUE,
        system_id INTEGER NOT NULL,
        model_name TEXT NOT NULL,
        vram_capacity_mib INTEGER,
        FOREIGN KEY (system_id) REFERENCES system_info(system_id)
    );
    '''

    CREATE_SYSTEM_INFO_TABLE = '''
    CREATE TABLE IF NOT EXISTS system_info (
        system_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ram_capacity INTEGER NOT NULL,
        disk_capacity INTEGER NOT NULL,
        total_vram_capacity_mib INTEGER
    );
    '''

    CREATE_GPU_STATUS_TABLE = '''
    CREATE TABLE IF NOT EXISTS gpu_status (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        gpu_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        p_state TEXT,
        temperature INTEGER,
        gpu_utilization INTEGER,
        memory_utilization INTEGER,
        clock_sm INTEGER,
        clock_memory INTEGER,
        clock_graphics INTEGER,
        power_usage INTEGER,
        memory_free_mib INTEGER,
        memory_used_mib INTEGER,
        pcie_rx INTEGER,
        pcie_tx INTEGER,
        session_id INTEGER,
        FOREIGN KEY (gpu_id) REFERENCES gpu_info(gpu_id),
        FOREIGN KEY (session_id) REFERENCES test_session(id)
    );
    '''

    CREATE_TEST_SESSION_TABLE = '''
    CREATE TABLE IF NOT EXISTS test_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_timestamp TEXT NOT NULL,
        end_timestamp TEXT,
        is_active INTEGER GENERATED ALWAYS AS (CASE WHEN end_timestamp IS NULL THEN 1 ELSE 0 END) STORED
    );
    '''

    # -=- Data Writing -=-
    WRITE_SYSTEM_INFO_RECORD = '''
    INSERT INTO system_info (
        ram_capacity,
        disk_capacity,
        total_vram_capacity_mib
    ) VALUES (?, ?, ?);
    '''

    WRITE_CPU_INFO_RECORD = '''
    INSERT INTO cpu_info (
        system_id,
        model_name,
        cores,
        min_frequency,
        max_frequency
    ) VALUES (?, ?, ?, ?, ?);
    '''

    WRITE_GPU_INFO_RECORD = '''
    INSERT INTO gpu_info (
        system_id,
        bus_id,
        model_name,
        vram_capacity_mib
    ) VALUES (?, ?, ?, ?);
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
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    '''

    # -=- Data Queries -=-
    FIND_LATEST_SYSTEM_ID = 'SELECT MAX(system_id) as latest_system_id FROM system_info;'
    FIND_GPU_ID_FROM_BUS_ID = 'SELECT gpu_id FROM gpu_info WHERE bus_id = ?;'
    FIND_ACTIVE_SESSION_ID = 'SELECT session_id FROM test_session WHERE is_active = 1;'
