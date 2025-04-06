import pynvml

from models.gpu_info import GPUInfo

try:
    import pyopencl as cl
except ImportError:
    cl = None


def get_gpu_info() -> [GPUInfo]:
    gpu_list = []
    skip_nvml = False

    # Attempt to capture information about NVIDIA GPUs using NVML:
    try:
        pynvml.nvmlInit()
    except pynvml.NVMLError as err:
        skip_nvml = True
        print('Failed to initialize NVML via pynvml: ', err)

    if not skip_nvml:
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            for idx in range(device_count):
                try:
                    # Select device by index:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(idx)

                    # Get name of device, decoding if required:
                    raw_name = pynvml.nvmlDeviceGetName(handle)
                    name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name

                    # Get total VRAM, coercing MiB:
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    vram_capacity_mib = int(memory_info.total // (1024 ** 2))

                    # Get bus ID for current GPU:
                    pci_info = pynvml.nvmlDeviceGetPciInfo(handle)
                    bus_id = pci_info.busId.decode() if isinstance(pci_info.busId, bytes) else pci_info.busId

                    # Append to device list, ready for return later:
                    gpu_list.append(GPUInfo(name=name, bus_id=bus_id, vram_capacity_mib=vram_capacity_mib))
                except pynvml.NVMLError as err:
                    print(f'Error retrieving info for GPU (index {idx}): {err}')
        finally:
            pynvml.nvmlShutdown()

    # Attempt to capture non-NVIDIA GPUs via OpenCL:
    if cl is not None:
        try:
            platforms = cl.get_platforms()

            for platform in platforms:
                devices = platform.get_devices(device_type=cl.device_type.GPU)
                for device in devices:
                    # Skip NVIDIA GPUs:
                    vendor = device.vendor
                    if 'NVIDIA' in vendor.upper():
                        continue

                    name = device.name.strip()
                    # In the case that a GPU was accounted for more than once, do not add to list.
                    if not any(gpu.name == name for gpu in gpu_list):
                        gpu_list.append(GPUInfo(name=name, vram_capacity_mib=None))

        except Exception as err:
            print('Error retrieving GPU info using OpenCL via pyopencl:', err)
    else:
        print('`pyopencl` is not installed; skipping non-NVIDIA GPU detection.')

    return gpu_list
