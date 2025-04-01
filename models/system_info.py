from marshmallow import Schema, fields, post_load

from models.cpu_info import CPUInfo, CPUInfoSchema
from models.gpu_info import GPUInfo, GPUInfoSchema


class SystemInfo:
    def __init__(self, cpu: CPUInfo, gpus: [GPUInfo], ram_capacity: int, disk_capacity: int):
        self.cpu = cpu
        self.gpus = gpus
        self.ram_capacity = ram_capacity
        self.disk_capacity = disk_capacity
        self.total_vram_capacity = sum(gpu.vram_capacity for gpu in gpus)

    def __repr__(self):
        return (
            f'<SystemInfo(cpu={self.cpu}, gpus={self.gpus}, '
            f'ram_capacity={self.ram_capacity}, disk_capacity={self.disk_capacity}, '
            f'total_vram_capacity={self.total_vram_capacity})>'
        )


class SystemInfoSchema(Schema):
    cpu = fields.List(fields.Nested(CPUInfoSchema), required=True)
    gpus = fields.List(fields.Nested(GPUInfoSchema), required=True)
    ram_capacity = fields.Integer(required=True)
    disk_capacity = fields.Integer(required=True)

    @post_load
    def make_system_info(self, data, **kwargs):
        return SystemInfo(**data)
