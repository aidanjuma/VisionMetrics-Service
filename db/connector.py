import sqlite3
from sqlite3 import Connection
from typing import Any

from enums.queries import FixedDBQuery


class DBConnector:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.__connection: Connection | None = None

    def connect(self) -> Connection:
        try:
            self.__connection = sqlite3.connect(self.db_file, check_same_thread=False)
            self.__connection.row_factory = sqlite3.Row
            self.__initialize_db()
        except sqlite3.Error as err:
            print(f'Error connecting to database {self.db_file}: {err}')
        return self.__connection

    def disconnect(self) -> None:
        if self.__connection:
            try:
                self.__connection.close()
                self.__connection = None
            except sqlite3.Error as err:
                print(f'Error disconnecting from database {self.db_file}: {err}')

    # TODO: Better error handling...
    def execute_query(self, query: FixedDBQuery, params: tuple = (), fetch: bool = False) -> list[Any] | None:
        try:
            cursor = self.__connection.cursor()
            cursor.execute(query.value, params)
            self.__connection.commit()

            if fetch:
                results = cursor.fetchall()
                return results if results or results != [] else None
        except sqlite3.Error as err:
            print(f'Error executing query "{query}": {err}')

    def __initialize_db(self) -> None:
        self.execute_query(FixedDBQuery.CREATE_CPU_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_GPU_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_SYSTEM_INFO_TABLE)
        self.execute_query(FixedDBQuery.CREATE_GPU_STATUS_TABLE)
        self.execute_query(FixedDBQuery.CREATE_TEST_SESSION_TABLE)
