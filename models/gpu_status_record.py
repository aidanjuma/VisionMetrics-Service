from marshmallow import Schema, fields

from models.gpu_info import GPUInfo


# TODO: Continue...

class GPUStatusRecord(GPUInfo):
    def __init__(self, name: str, bus_id: str, vram_capacity_mib: int, memory_free_mib: int, memory_used_mib: int):
        super().__init__(name, bus_id, vram_capacity_mib)

        self.memory_free_mib = memory_free_mib
        self.memory_used_mib = memory_used_mib


class GPUStatusRecordSchema(Schema):
    name = fields.String(required=True)
    bus_id = fields.String(required=False, default=None)
    vram_capacity_mib = fields.Integer(required=True)
    memory_used_mib = fields.Integer(required=True)
