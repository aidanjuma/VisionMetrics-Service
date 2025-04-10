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
        system_ram_used_mib INTEGER,
        system_ram_used_percentage INTEGER,
        FOREIGN KEY (gpu_id) REFERENCES gpu_info(gpu_id),
        FOREIGN KEY (session_id) REFERENCES test_session(id)
    );
    '''

    # Written to by backend...
    CREATE_USE_CASE_TABLE = '''
    CREATE TABLE IF NOT EXISTS use_case (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_session_id INTEGER,
        position_in_queue INTEGER,
        script_filename TEXT NOT NULL,
        sha256_checksum TEXT NOT NULL,
        start_timestamp TEXT,
        end_timestamp TEXT,
        is_active INTEGER GENERATED ALWAYS AS (CASE WHEN end_timestamp IS NULL THEN 0 ELSE 1 END) STORED,
        FOREIGN KEY (test_session_id) REFERENCES test_session(id)
    );
    '''

    UPDATE_USE_CASE_POSITION_IN_QUEUE_ON_TEST_SESSION_ASSIGNMENT = '''
    CREATE TRIGGER IF NOT EXISTS update_position_on_test_session_change
    AFTER UPDATE OF test_session_id ON use_case
    FOR EACH ROW
    WHEN (NEW.test_session_id IS NOT OLD.test_session_id) OR 
         (NEW.test_session_id IS NOT NULL AND OLD.test_session_id IS NULL)
    BEGIN
        UPDATE use_case
        SET position_in_queue = (
            SELECT COALESCE(MAX(position_in_queue), 0) + 1
            FROM use_case
            WHERE test_session_id = NEW.test_session_id AND id != NEW.id
        )
        WHERE id = NEW.id;
    END;
    '''

    # Written to by backend...
    CREATE_TEST_SESSION_TABLE = '''
    CREATE TABLE IF NOT EXISTS test_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_timestamp TEXT NOT NULL,
        end_timestamp TEXT,
        is_active INTEGER GENERATED ALWAYS AS (CASE WHEN end_timestamp IS NULL THEN 0 ELSE 1 END) STORED
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
        session_id,
        system_ram_used_mib,
        system_ram_used_percentage
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    '''

    # -=- Data Queries -=-
    FIND_LATEST_SYSTEM_ID = 'SELECT MAX(system_id) as latest_system_id FROM system_info;'
    FIND_GPU_ID_FROM_BUS_ID = 'SELECT gpu_id FROM gpu_info WHERE bus_id = ?;'
    FIND_ACTIVE_SESSION_ID = 'SELECT id FROM test_session WHERE is_active = 1;'
