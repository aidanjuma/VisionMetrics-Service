import sqlite3
from sqlite3 import Connection

from enums.queries import FixedDBQuery


class DBConnector:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.connection: Connection | None = None

    def connect(self) -> Connection:
        try:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.__initialize_db()
        except sqlite3.Error as err:
            print(f'Error connecting to database {self.db_file}: {err}')
        return self.connection

    # TODO: Better error handling...
    def execute_query(self, query: FixedDBQuery, params: tuple = ()):
        try:
            cursor = self.connection.cursor()
            cursor.execute(str(query), params)
            self.connection.commit()
        except sqlite3.Error as err:
            print(f'Error executing query "{query}": {err}')

    def __initialize_db(self) -> None:
        self.execute_query(FixedDBQuery.CREATE_CPU_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_GPU_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_SYSTEM_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_GPU_STATUS_TABLE)
