import os

import db.connector as db

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

    connector.connect()
    # connector.disconnect()

    # TODO: Continue... (according to architecture decisions!)
