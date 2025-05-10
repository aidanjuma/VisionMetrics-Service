import subprocess
import os

from models.managed_vllm_instance import ManagedVllmInstance


class ProcessManager:
    def __init__(self):
        self.managed_processes: dict[int, ManagedVllmInstance] = {}

    def __del__(self):
        self.__cleanup()

    def launch_vllm_instance(self, mig_device_uuid: str, model_name_or_path: str, port: int,
                             tensor_parallel_size: int = 1, api_host: str = '0.0.0.0'):
        if port in self.managed_processes:
            print(f'Port {port} is already in use by a managed vLLM instance.')
            return None

        command = [
            'python3', '-m', 'vllm.entrypoints.openai.api_server',
            '--host', str(api_host),
            '--port', str(port),
            '--model', str(model_name_or_path),
            '--tensor-parallel-size', str(tensor_parallel_size)
        ]

        log_file_out = f'vllm_port_{port}_out.log'
        log_file_err = f'vllm_port_{port}_err.log'

        print(
            f'Launching vLLM on MIG UUID <{mig_device_uuid}>, Port <{port}>, Model <{model_name_or_path}>')

        try:
            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = mig_device_uuid

            with open(log_file_out, 'wb') as stdout, open(log_file_err, 'wb') as stderr:
                process = subprocess.Popen(
                    command, stdout=stdout, stderr=stderr, env=env)

            vllm_instance_data = ManagedVllmInstance(
                port=port,
                process=process,
                mig_uuid=mig_device_uuid,
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
        if port not in self.managed_processes:
            print(f'No managed vLLM instance found for port {port}.')
            return False

        managed_instance = self.managed_processes[port]
        process_to_terminate = managed_instance.process
        print(
            f'Terminating vLLM instance on port <{port}> (PID <{process_to_terminate.pid}>)...')

        try:
            process_to_terminate.terminate()
            process_to_terminate.wait(timeout=10)
            print(f'vLLM instance on port <{port}> terminated.')
        except subprocess.TimeoutExpired:
            print(
                f'vLLM instance on port <{port}> did not terminate gracefully, forcing kill...')
            process_to_terminate.kill()
            process_to_terminate.wait()
            print(f'vLLM instance on port <{port}> killed.')
        except Exception as err:
            print(
                f'Error during termination of vLLM PID <{process_to_terminate.pid}>: {err}')
            return False
        finally:
            del self.managed_processes[port]
        return True

    def __cleanup(self):
        ports_to_terminate = list(self.managed_processes.keys())
        for port in ports_to_terminate:
            print(f'Terminating vLLM on port {port} during clean-up...')
            self.terminate_vllm_instance(port)
