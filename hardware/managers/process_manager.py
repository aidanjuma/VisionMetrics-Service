import subprocess
import os
import time
from typing import List

from models.managed_vllm_instance import ManagedVllmInstance


class ProcessManager:
    def __init__(self):
        self.log_dir = os.path.join('logs', 'vllm')
        os.makedirs(self.log_dir, exist_ok=True)

        self.managed_processes: dict[int, ManagedVllmInstance] = {}

    def __del__(self):
        self.__cleanup()

    def launch_vllm_instance(self, mig_device_uuids: List, model_name_or_path: str, port: int,
                             tensor_parallel_size: int = 1, api_host: str = '0.0.0.0'):
        # Check if the port is already in use by a managed vLLM instance:
        if port in self.managed_processes:
            print(f'Port {port} is already in use by a managed vLLM instance.')
            return None

        # Define the command that will be used to launch the vLLM instance:
        command = [
            'python3', '-m', 'vllm.entrypoints.openai.api_server',
            '--host', str(api_host),
            '--port', str(port),
            '--model', str(model_name_or_path),
            '--tensor-parallel-size', str(tensor_parallel_size)
        ]

        # Define paths leading to the log files that will be created by the vLLM instance:
        timestamp = int(time.time())
        log_file_out = os.path.join(
            self.log_dir, f'vllm_port_{port}_out_{timestamp}.log')
        log_file_err = os.path.join(
            self.log_dir, f'vllm_port_{port}_err_{timestamp}.log')

        print(
            f'Launching vLLM on MIG UUID <{mig_device_uuids}>, Port <{port}>, Model <{model_name_or_path}>')

        # Try to launch the vLLM instance:
        try:
            env = os.environ.copy()
            # Expose only desired MIG profiles to the vLLM instance.
            env['CUDA_VISIBLE_DEVICES'] = self.__list_to_comma_separated_string(
                mig_device_uuids)

            with open(log_file_out, 'wb') as stdout, open(log_file_err, 'wb') as stderr:
                process = subprocess.Popen(
                    command, stdout=stdout, stderr=stderr, env=env)

            vllm_instance_data = ManagedVllmInstance(
                port=port,
                process=process,
                mig_uuids=mig_device_uuids,
                model_name_or_path=model_name_or_path,
                command=command
            )
            self.managed_processes[port] = vllm_instance_data

            print(
                f'vLLM instance for port <{port}> started with PID <{process.pid}>')

            return process.pid

        except Exception as err:
            print(f'Error launching vLLM instance on port {port}: {err}')
            return None

    def terminate_vllm_instance(self, port: int) -> bool:
        # Check if the port is not in use by a managed vLLM instance:
        if port not in self.managed_processes:
            print(f'No managed vLLM instance found for port {port}.')
            return False

        # Select the managed vLLM instance that is associated with the port:
        managed_instance = self.managed_processes[port]
        process_to_terminate = managed_instance.process
        print(
            f'Terminating vLLM instance on port <{port}> (PID <{process_to_terminate.pid}>)...')

        # Try to terminate the vLLM service gracefully:
        try:
            process_to_terminate.terminate()
            process_to_terminate.wait(timeout=10)
            print(f'vLLM instance on port <{port}> terminated.')

        # If the vLLM service did not terminate gracefully, force kill it:
        except subprocess.TimeoutExpired:
            print(
                f'vLLM instance on port <{port}> did not terminate gracefully, forcing kill...')
            process_to_terminate.kill()
            process_to_terminate.wait()
            print(f'vLLM instance on port <{port}> killed.')

        # If an error occurs during the termination of the vLLM service, return False:
        except Exception as err:
            print(
                f'Error during termination of vLLM PID <{process_to_terminate.pid}>: {err}')
            return False
        finally:
            # Remove the managed vLLM instance from the dictionary of managed processes:
            del self.managed_processes[port]

        return True

    def __cleanup(self):
        ports_to_terminate = list(self.managed_processes.keys())
        for port in ports_to_terminate:
            print(f'Terminating vLLM on port {port} during clean-up...')
            self.terminate_vllm_instance(port)

    def __list_to_comma_separated_string(list: List) -> str:
        return ','.join(list)
