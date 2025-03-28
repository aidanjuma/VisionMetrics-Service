import subprocess


def get_core_temperature_nvidia_gpu() -> []:
    temperature = subprocess.run(
        ['nvidia-smi', '--query-gpu=timestamp,name,pci.bus_id,temperature.gpu', '--format=csv,noheader'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )

    # TODO: Implant/link in with custom model(s).
