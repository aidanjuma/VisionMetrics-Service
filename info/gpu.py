import pynvml

from models.gpu_info import GPUInfo


def get_gpu_info() -> []:
    gpu_list = []

    try:
        pynvml.nvmlInit()
    except pynvml.NVMLError as err:
        print('Failed to initialize NVML via pynvml: ', err)
        return gpu_list

    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for idx in range(device_count):
            try:
                # Select device by index:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)

                # Get name of device, decoding if required:
                raw_name = pynvml.nvmlDeviceGetName(handle)
                name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name

                # Get total VRAM, coercing GiB:
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_capacity = int(memory_info.total // (1024 ** 3))

                # Append to device list, ready for return later:
                gpu_list.append(GPUInfo(name=name, vram_capacity=vram_capacity))
            except pynvml.NVMLError as err:
                print(f'Error retrieving info for GPU (index {idx}): {err}')
    finally:
        pynvml.nvmlShutdown()

    return gpu_list
