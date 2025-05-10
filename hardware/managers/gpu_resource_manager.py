import subprocess
import time

from pynvml import *

from enums.mig_status import MIGStatus
from models.gpu_info import GPUInfo
from models.managed_gpu_instance import ManagedGpuInstance


class GPUResourceManager:
    def __init__(self, gpu_info: GPUInfo):
        self.gpu_info = gpu_info
        self.physical_gpu_handle = None
        self.managed_gis: dict[str, ManagedGpuInstance] = {}

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

    def __del__(self):
        # If the physical_gpu_handle is still valid, call for clean-up.
        if hasattr(self, 'physical_gpu_handle') and self.physical_gpu_handle:
            self.__cleanup(destroy_managed_gis=False)

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
                            'name': profile_info.name.decode() if hasattr(profile_info,
                                                                          'name') else f'Profile-{profile_info.id}'
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

    def get_all_mig_device_uuids(self) -> list[str] | None:
        # Lists UUIDs of all active MIG 'devices' on this GPU.
        if not self.physical_gpu_handle:
            print(
                f'[{self.gpu_info.bus_id if self.gpu_info else 'Unknown GPU'}] Error: Physical GPU handle not initialized.')
            return None

        # Get the parent GPU's bus ID and UUID:
        parent_gpu_bus_id, parent_physical_gpu_uuid = self.__get_parent_gpu_details()
        if not parent_gpu_bus_id or not parent_physical_gpu_uuid:
            return None

        # Check the MIG status of the parent GPU:
        mig_status = self.__check_and_log_mig_status(parent_gpu_bus_id)
        if mig_status == MIGStatus.NOT_SUPPORTED:
            return None

        uuids = []
        try:
            uuids = self.__enumerate_mig_children_uuids(
                parent_gpu_bus_id, parent_physical_gpu_uuid)
        except NVMLError as err:
            log_error_gpu_id = parent_gpu_bus_id or \
                (self.gpu_info.bus_id if self.gpu_info else 'Unknown GPU')
            print(f'[{log_error_gpu_id}] Critical NVMLError during MIG device enumeration: {err}. '
                  'Cannot reliably list MIG devices.')
            return None

        if not uuids:
            fallback_uuids = self.__get_fallback_uuids(parent_gpu_bus_id)
            if fallback_uuids is not None:
                return fallback_uuids

        # Reached if enumeration found nothing AND fallback also found nothing/no fallback available.
        print(f'[{parent_gpu_bus_id}] No MIG devices (GIs/CIs) found for this GPU (UUID: {parent_physical_gpu_uuid}).')

        return sorted(list(set(uuids)))

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

    def __get_parent_gpu_details(self) -> tuple[str | None, str | None]:
        '''Retrieves PCI bus ID and UUID for the physical GPU of this manager instance.'''
        try:
            parent_pci_info = nvmlDeviceGetPciInfo(self.physical_gpu_handle)
            bus_id = parent_pci_info.busId.decode('utf-8')
            uuid = nvmlDeviceGetUUID(self.physical_gpu_handle).decode('utf-8')
            return bus_id, uuid
        except NVMLError as err:
            error_source_gpu_id = self.gpu_info.bus_id if self.gpu_info else 'Unknown GPU (handle exists)'
            print(
                f'[{error_source_gpu_id}] NVMLError while retrieving parent GPU details: {err}.')
            return None, None

    def __check_and_log_mig_status(self, parent_gpu_bus_id: str) -> MIGStatus:
        '''Checks and logs MIG capability and status for the parent GPU.'''
        if not self.__is_mig_capable():
            print(
                f'[{parent_gpu_bus_id}] This GPU does not support MIG mode. Cannot list MIG devices.')
            return MIGStatus.NOT_SUPPORTED

        # Check if MIG mode is enabled:
        try:
            current_mode, _ = nvmlDeviceGetMigMode(self.physical_gpu_handle)
            if current_mode != NVML_DEVICE_MIG_ENABLE:
                print(
                    f'[{parent_gpu_bus_id}] MIG mode is not currently enabled on this GPU.')
                return MIGStatus.NOT_ENABLED
            return MIGStatus.ENABLED

        # If we can't check MIG mode, assume it is enabled and continue.
        except NVMLError as mig_error:
            print(
                f'[{parent_gpu_bus_id}] Warning: Could not determine MIG mode due to NVML error: {mig_error}.')
            return MIGStatus.ERROR_CHECKING_MODE

    def __enumerate_mig_children_uuids(self, parent_gpu_bus_id: str, parent_physical_gpu_uuid: str) -> list[str]:
        '''Enumerates NVML devices and filters for MIG children of the specified parent GPU.'''
        discovered_uuids = []
        device_count = nvmlDeviceGetCount()

        for idx in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(
                idx)
            try:
                current_device_pci_info = nvmlDeviceGetPciInfo(handle)
                current_device_bus_id = current_device_pci_info.busId.decode(
                    'utf-8')
                current_device_uuid = nvmlDeviceGetUUID(handle).decode('utf-8')

                # If the current device ID is the parent GPU's ID, check if it is a MIG child.
                if current_device_bus_id == parent_gpu_bus_id:
                    if current_device_uuid != parent_physical_gpu_uuid and \
                            current_device_uuid.startswith('MIG-'):
                        if current_device_uuid not in discovered_uuids:
                            discovered_uuids.append(current_device_uuid)
            except NVMLError:
                continue

        return discovered_uuids

    def __get_fallback_uuids(self, parent_gpu_bus_id_for_log: str) -> list[str] | None:
        '''Returns sorted list of managed GI UUIDs if enumeration found none, else None.'''
        if self.managed_gis:
            log_gpu_id = parent_gpu_bus_id_for_log or \
                (self.gpu_info.bus_id if self.gpu_info else 'Unknown GPU')

            print(
                f'[{log_gpu_id}] No MIG devices auto-discovered via system enumeration for this GPU.')

            return sorted(list(self.managed_gis.keys()))

        return None

    def __cleanup(self, destroy_managed_gis=True):
        # Destroy managed GIs if requested:
        if destroy_managed_gis:
            # Iterate over a copy of managed_gis keys as self.destroy_gi will modify the dictionary
            managed_gis_to_destroy = list(self.managed_gis.keys())
            for gi_uuid in managed_gis_to_destroy:
                # destroy_gi already checks if gi_uuid is in self.managed_gis before attempting deletion
                print(f'Destroying managed GI {gi_uuid} during clean-up...')
                # destroy_gi removes from self.managed_gis upon success
                self.destroy_gi(gi_uuid)

        try:
            nvmlShutdown()
            print('NVML shut down by clean-up process.')
        except NVMLError as err:
            print(f'Error during NVML shutdown: {err}')
