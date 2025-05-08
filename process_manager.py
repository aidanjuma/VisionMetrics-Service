import os
import subprocess
import time
from pynvml import *

from models.gpu_info import GPUInfo
from models.managed_gpu_instance import ManagedGpuInstance
from models.managed_vllm_instance import ManagedVllmInstance


class ProcessManager:
    def __init__(self, gpu_info: GPUInfo):
        self.gpu_info = gpu_info
        self.physical_gpu_handle = None
        self.managed_gis: dict[str, ManagedGpuInstance] = {}
        self.managed_processes: dict[int, ManagedVllmInstance] = {}

        # Attempt to initialize NVML; handle error(s) if it fails:
        try:
            nvmlInit()
            self.physical_gpu_handle = nvmlDeviceGetHandleByPciBusId(
                self.gpu_info.bus_id.encode())
        except NVMLError as err:
            print(
                f'Error during NVML initialization or device access for GPU {self.gpu_info.bus_id}: {err}')
            # Attempt to gracefully shutdown NVML, in the case that it was somehow partially initialized.
            try:
                nvmlShutdown()
            # Log these secondary error, but the original error 'err' is the one to be propagated.
            except NVMLError as shutdown_error:
                print(
                    f'Further NVMLError encountered during nvmlShutdown cleanup for GPU {self.gpu_info.bus_id} after initial error: {shutdown_error}')
            except Exception as unexpected_shutdown_error:
                print(
                    f'Unexpected error encountered during nvmlShutdown cleanup for GPU {self.gpu_info.bus_id} after initial error: {unexpected_shutdown_error}')

            # Re-raise the original NVMLError that prompted this cleanup attempt.
            raise

    def enable_mig_mode(self) -> bool:
        # Check if the GPU supports MIG mode; only continue if it does.
        if not self.__is_mig_capable():
            print(
                f'GPU {self.gpu_info.bus_id} ({self.gpu_info.name}) does not support MIG mode.')
            return False

        try:
            # Try to get the current MIG mode; if enabled, return True.
            current_mode, pending_mode = nvmlDeviceGetMigMode(
                self.physical_gpu_handle)
            if current_mode == NVML_DEVICE_MIG_ENABLE:
                print('MIG mode is already enabled.')
                return True

            # ...otherwise, attempt to enable it.
            print('Attempting to enable MIG mode...')
            nvmlDeviceSetMigMode(self.physical_gpu_handle,
                                 NVML_DEVICE_MIG_ENABLE)
            print(
                'MIG mode enable requested. This may take a moment and might require a GPU reset.')

            # Wait for MIG mode to become active or for a pending change to clear; nvidia-smi often triggers a GPU reset if one isn't already pending.
            timeout_seconds = 30
            start_time = time.time()
            while (time.time() - start_time) < timeout_seconds:
                current_mode, pending_mode = nvmlDeviceGetMigMode(
                    self.physical_gpu_handle)

                if current_mode == NVML_DEVICE_MIG_ENABLE and pending_mode == NVML_DEVICE_MIG_DISABLE:
                    print(
                        'MIG mode is enabled, but a disable is pending. Waiting for disable to complete...')

                if current_mode == NVML_DEVICE_MIG_ENABLE:
                    print('MIG mode successfully enabled.')
                    return True

                # Wait a second before trying again...
                time.sleep(1)

            print(
                f'Timeout waiting for MIG mode to enable. Current: {current_mode}, Pending: {pending_mode}')
            return False

        except NVMLError as err:
            print(
                f'Error enabling MIG mode: {err}. Ensure GPU is idle and script has root privileges.')
            return False

    def list_gi_profiles(self) -> list[dict] | None:
        # Check if the GPU supports MIG mode; only continue if it does.
        if not self.__is_mig_capable():
            print(
                f'GPU {self.gpu_info.bus_id} ({self.gpu_info.name}) does not support MIG mode. Cannot list profiles.')
            return None

        # GPU supports MIG mode, so we can attempt to list the profiles.
        profiles = []
        try:
            idx = 0
            while True:
                # Attempt to get the profile info for the current index.
                try:
                    profile_info = nvmlDeviceGetGpuInstanceProfileInfo(
                        self.physical_gpu_handle, idx)

                    # Valid profiles usually have resources; sliceCount is a good indicator for GIs.
                    if profile_info.sliceCount > 0:
                        profiles.append({
                            'profile_index': idx,
                            'id': profile_info.id,
                            'slice_count': profile_info.sliceCount,
                            'memory_mb': profile_info.memorySizeMB,
                            'name': profile_info.name.decode() if hasattr(profile_info, 'name') else f'Profile-{profile_info.id}'
                        })

                except NVMLError as err:
                    # If the profile index is out of range or not found, break the loop.
                    if err.value == NVML_ERROR_INVALID_ARGUMENT or err.value == NVML_ERROR_NOT_FOUND:
                        break

                    # Otherwise, log the error and continue.
                    print(
                        f'Warning: Could not get profile info for index {idx}: {err}')
                idx += 1

        except NVMLError as err:
            print(f'Error listing GI profiles: {err}')

        # Return the list of profiles.
        return None if not profiles else profiles

    def create_gi(self, profile_id: int) -> str | None:
        # Check if the GPU supports MIG mode; only continue if it does.
        if not self.__is_mig_capable():
            print(
                f'GPU {self.gpu_info.bus_id} ({self.gpu_info.name}) does not support MIG mode. Cannot create GI.')
            return None

        # GPU supports MIG mode, so we can attempt to create a GI.
        try:
            # Check if MIG mode is enabled.
            current_mode, _ = nvmlDeviceGetMigMode(self.physical_gpu_handle)
            if current_mode != NVML_DEVICE_MIG_ENABLE:
                print('MIG mode is not enabled. Please enable it first.')
                return None

            # Attempt to create the GI.
            gi_handle = nvmlDeviceCreateGpuInstance(
                self.physical_gpu_handle, profile_id)
            gi_info = nvmlGpuInstanceGetInfo(gi_handle)
            gi_uuid = gi_info.uuid.decode()

            # Store the ManagedGpuInstance object.
            self.managed_gis[gi_uuid] = ManagedGpuInstance(
                uuid=gi_uuid, handle=gi_handle)
            print(
                f'Successfully created GPU Instance with Profile ID {profile_id}, GI UUID: {gi_uuid}')
            return gi_uuid
        except NVMLError as err:
            print(
                f'Error creating GPU Instance with profile ID {profile_id}: {err}')
            return None

    def destroy_gi(self, gi_uuid) -> bool:
        # Check if the GI is managed by this manager; if not, return False - GI could not be destroyed.
        if gi_uuid not in self.managed_gis:
            print(
                f'GPU Instance with UUID {gi_uuid} not managed or not found.')
            return False

        # Continue on to destroy the GI, since it is managed by this manager.
        managed_gi = self.managed_gis[gi_uuid]
        try:
            # Before destroying GI, ensure any associated CIs are destroyed:
            self.__destroy_compute_instances_on_gi(managed_gi, gi_uuid)

            nvmlGpuInstanceDestroy(managed_gi.handle)
            print(f'Successfully destroyed GPU Instance UUID: {gi_uuid}')
            del self.managed_gis[gi_uuid]

            return True

        except NVMLError as err:
            print(f'Error destroying GPU Instance UUID {gi_uuid}: {err}')
            return False

    def get_all_mig_device_uuids(self):
        '''Lists UUIDs of all active MIG devices (GIs/CIs) visible to CUDA.'''
        uuids = []
        try:
            # This method of iterating all devices and checking their UUID might be complex
            # if we only care about MIG devices from the *managed* physical GPU.
            # The original code iterated all nvmlDeviceGetCount() devices.
            # For now, let's assume we might need to see all system-wide MIG UUIDs.
            # If this needs to be scoped to MIG devices *on this specific physical_gpu_handle*,
            # the logic to discover them would need to be more targeted, perhaps using
            # nvmlDeviceGetMigDeviceHandleByIndex within a loop on the parent physical_gpu_handle.

            # The previous heuristic: 'MIG' in uuid or idx >= nvmlDeviceGetMaxMigDeviceCount(self.physical_gpu_handle)
            # This needs self.physical_gpu_handle which is correct.

            # Let's try to get Max MIG device count on the specific physical GPU
            # to help identify potential MIG devices.
            max_mig_devices_on_this_gpu = 0
            try:
                max_mig_devices_on_this_gpu = nvmlDeviceGetMaxMigDeviceCount(
                    self.physical_gpu_handle)
            except NVMLError:  # Potentially not MIG capable or other issue
                pass

            device_count = nvmlDeviceGetCount()
            for idx in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(idx)
                try:
                    uuid = nvmlDeviceGetUUID(handle).decode()
                    # Refined Heuristic:
                    # A device is a MIG device if:
                    # 1. 'MIG' is in its UUID (common convention for MIG device UUIDs)
                    # OR
                    # 2. It's a handle that NVML considers a MIG device.
                    #    We can check this by trying a MIG-specific call that fails on non-MIG devices
                    #    or succeeds/fails characteristically on MIG device handles.
                    #    For instance, nvmlDeviceGetMigMode fails on an actual MIG *device* handle
                    #    with NVML_ERROR_NOT_SUPPORTED or NVML_ERROR_INVALID_ARGUMENT because
                    #    MIG mode is a property of the parent physical GPU, not the MIG device itself.

                    is_mig_device_type = False
                    try:
                        # This call is expected to fail on a MIG device handle.
                        nvmlDeviceGetMigMode(handle)
                    except NVMLError as e_mig_check:
                        if e_mig_check.value == NVML_ERROR_NOT_SUPPORTED or e_mig_check.value == NVML_ERROR_INVALID_ARGUMENT:
                            # This suggests 'handle' could be a MIG device handle.
                            # Further check: ensure this MIG device belongs to our managed physical GPU.
                            # This is tricky. For now, we'll keep the broader check.
                            # A robust way would be to get parent GPU of this MIG device and match its UUID/bus_id.
                            is_mig_device_type = True

                    # Alternative: Check if 'MIG-' is prefix of UUID, which is more common for actual MIG device UUIDs
                    # nvidia-smi -L shows these UUIDs as "MIG-..."
                    if uuid.startswith('MIG-'):
                        is_mig_device_type = True

                    if is_mig_device_type:
                        uuids.append(uuid)

                except NVMLError:  # Skip devices that can't get UUID or other issues
                    continue
        except NVMLError as err:
            print(f'Error enumerating device UUIDs: {err}')

        # If no MIG devices found this way, rely on created GI UUIDs from *this* manager
        if not uuids and self.managed_gis:
            print('Could not auto-discover MIG device UUIDs for CUDA_VISIBLE_DEVICES, using managed GI UUIDs as fallback.')
            # These are GIs created on the current physical GPU
            return list(self.managed_gis.keys())
        if not uuids:
            print(
                'No MIG devices found. Ensure GIs/CIs are created and MIG mode is active on the target GPU.')
        return uuids

    def launch_vllm_instance(self, mig_device_uuid, model_name_or_path, port,
                             tensor_parallel_size=1, api_host='0.0.0.0', **vllm_kwargs):
        if port in self.managed_processes:
            print(f'Port {port} is already in use by a managed vLLM instance.')
            return None

        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = mig_device_uuid

        # Construct vLLM command
        # Basic command, user can pass more via vllm_kwargs
        command = [
            'python', '-m', 'vllm.entrypoints.openai.api_server',
            '--host', str(api_host),
            '--port', str(port),
            '--model', str(model_name_or_path),
            '--tensor-parallel-size', str(tensor_parallel_size)
        ]

        # Add any additional vLLM arguments
        for key, value in vllm_kwargs.items():
            command.append(f'--{key.replace('_', '-')}')
            command.append(str(value))

        log_file_out = f'vllm_port_{port}_out.log'
        log_file_err = f'vllm_port_{port}_err.log'

        print(
            f'Launching vLLM on MIG UUID {mig_device_uuid}, Port {port}, Model {model_name_or_path}')
        print(f'Command: {' '.join(command)}')
        print(f'Output log: {log_file_out}, Error log: {log_file_err}')

        try:
            # Using Popen for non-blocking execution
            # Redirect stdout and stderr to log files
            with open(log_file_out, 'wb') as fout, open(log_file_err, 'wb') as ferr:
                process = subprocess.Popen(
                    command, env=env, stdout=fout, stderr=ferr)

            # Create and store ManagedVllmInstance object
            vllm_instance_data = ManagedVllmInstance(
                port=port,
                process=process,
                mig_uuid=mig_device_uuid,
                model_name_or_path=model_name_or_path,
                command=command
            )
            self.managed_processes[port] = vllm_instance_data
            print(
                f'vLLM instance for port {port} started with PID {process.pid}.')
            return process.pid
        except Exception as err:
            print(f'Error launching vLLM instance on port {port}: {err}')
            return None

    def terminate_vllm_instance(self, port):
        if port not in self.managed_processes:
            print(f'No managed vLLM instance found for port {port}.')
            return False

        managed_instance = self.managed_processes[port]
        process_to_terminate = managed_instance.process
        print(
            f'Terminating vLLM instance on port {port} (PID {process_to_terminate.pid})...')

        try:
            process_to_terminate.terminate()  # Send SIGTERM
            process_to_terminate.wait(timeout=10)  # Wait for graceful shutdown
            print(f'vLLM instance on port {port} terminated.')
        except subprocess.TimeoutExpired:
            print(
                f'vLLM instance on port {port} did not terminate gracefully, forcing kill...')
            process_to_terminate.kill()  # Send SIGKILL
            process_to_terminate.wait()
            print(f'vLLM instance on port {port} killed.')
        except Exception as err:
            print(
                f'Error during termination of vLLM PID {process_to_terminate.pid}: {err}')
            return False
        finally:
            del self.managed_processes[port]
        return True

    def get_vllm_instance_status(self, port):
        if port not in self.managed_processes:
            return 'Not managed'
        managed_instance = self.managed_processes[port]
        process_to_check = managed_instance.process
        poll_status = process_to_check.poll()
        if poll_status is None:
            return f'Running (PID {process_to_check.pid})'
        return f'Exited with code {poll_status} (PID {process_to_check.pid})'

    def __destroy_compute_instances_on_gi(self, managed_gi: ManagedGpuInstance, gi_uuid: str):
        try:
            # Iterate through all possible CI profiles to find and destroy active CIs.
            ci_profile_idx = 0
            while True:
                try:
                    # Attempt to get CI profile info for NVML_COMPUTE_INSTANCE_ENGINE_PROFILE_SHARED profile:
                    ci_prof_info = nvmlGpuInstanceGetComputeInstanceProfileInfo(
                        managed_gi.handle, ci_profile_idx, NVML_COMPUTE_INSTANCE_ENGINE_PROFILE_SHARED)

                    # Get count of CIs for the current profile:
                    ci_count_for_profile = nvmlGpuInstanceGetComputeInstances(
                        managed_gi.handle, ci_prof_info.id, 0)

                    if ci_count_for_profile > 0:
                        # If CIs exist, get their handles:
                        ci_handles = nvmlGpuInstanceGetComputeInstances(
                            managed_gi.handle, ci_prof_info.id, ci_count_for_profile)

                        for ci_handle in ci_handles:
                            try:
                                print(
                                    f'Destroying Compute Instance (handle: {ci_handle}) on GI {gi_uuid}')
                                nvmlComputeInstanceDestroy(ci_handle)
                            except NVMLError as ci_destroy_err:
                                print(
                                    f'Error destroying Compute Instance (handle: {ci_handle}) on GI {gi_uuid}: {ci_destroy_err}')

                except NVMLError as err:
                    # Break loop if profile index is invalid or no more profiles found.
                    if err.value == NVML_ERROR_INVALID_ARGUMENT or err.value == NVML_ERROR_NOT_FOUND:
                        break
                    # If profile not supported by this GI, continue to next profile index.
                    elif err.value == NVML_ERROR_NOT_SUPPORTED:
                        ci_profile_idx += 1
                        continue
                    print(
                        f'Error enumerating CI profile {ci_profile_idx} for GI {gi_uuid}: {err}')
                    break

                ci_profile_idx += 1

        except NVMLError as err:
            # Log error if iterating or destroying CIs fails.
            print(
                f'Could not fully iterate or destroy CIs on GI {gi_uuid} due to NVML error: {err}')
        except Exception as err:
            print(
                f'An unexpected error occurred during CI cleanup for GI {gi_uuid}: {err}')

    def __is_mig_capable(self):
        try:
            # MIG mode functions will fail on non-MIG GPUs (MIG supported by Ampere and later).
            nvmlDeviceGetMigMode(self.physical_gpu_handle)
            return True
        except NVMLError as err:
            if err.value == NVML_ERROR_NOT_SUPPORTED:
                return False

            # Assume not capable if we can't verify.
            print(
                f'Could not definitively determine MIG capability due to NVML error: {err}. Assuming not capable.')
            return False

    def __cleanup(self, destroy_created_gis=True):
        # Terminate all managed vLLM processes:
        ports_to_terminate = list(self.managed_processes.keys())
        for port in ports_to_terminate:
            print(f'Terminating vLLM on port {port} during clean-up...')
            self.terminate_vllm_instance(port)

        # Destroy managed GIs if requested:
        if destroy_created_gis:
            gis_to_destroy = list(self.managed_gis.keys())
            for gi_uuid in gis_to_destroy:
                print(f'Destroying GI {gi_uuid} during clean-up...')
                self.destroy_gi(gi_uuid)

        # Disable MIG mode if it was enabled by this manager:
        try:
            nvmlShutdown()
            print('NVML shut down by clean-up process.')
        except NVMLError as err:
            print(f'Error during NVML shutdown: {err}')

    def __del__(self):
        # If the physical_gpu_handle is still valid, call for cleanup().
        if hasattr(self, 'physical_gpu_handle') and self.physical_gpu_handle:
            self.__cleanup(destroy_created_gis=False)
