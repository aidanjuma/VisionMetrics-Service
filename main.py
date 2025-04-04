import os
import time
from sqlite3 import Connection

import db.connector as db
from enums.queries import FixedDBQuery
from info.collection import collect_system_info
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

    # Write static system information to disk:
    connector.execute_query(FixedDBQuery.WRITE_SYSTEM_INFO_RECORD, system_info_record)
    latest_system_id: int = connector.execute_query(FixedDBQuery.FIND_LATEST_SYSTEM_ID, fetch=True)[0][0]

    # TODO: Continue writing/collecting relevant data.

    try:
        while True:
            # TODO: Collect GPU logs...
            time.sleep(1)
    except KeyboardInterrupt:
        print('Log collection stopped by user.')
    finally:
        connector.disconnect()
