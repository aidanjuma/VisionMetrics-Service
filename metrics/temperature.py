import platform

from models.temperature_group import TemperatureGroup


def get_temperatures() -> [TemperatureGroup]:
    # psutil.sensors_temperatures() only supports Linux, and that's all I need for now.
    if platform.system() != 'Linux':
        print('Temperature monitoring is only supported on Linux at this time.')

    # TODO: Spin up a virtual machine with an NVIDIA GPU to be able to write logic properly.
