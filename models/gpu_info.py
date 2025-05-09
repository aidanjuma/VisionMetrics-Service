from marshmallow import Schema, fields, post_load


class GPUInfo:
    def __init__(self, name: str, physical_gpu_index: int | None = None, vram_capacity_mib: int | None = None,
                 bus_id: str | None = None):
        self.name = name
        self.physical_gpu_index = physical_gpu_index
        self.vram_capacity_mib = vram_capacity_mib
        self.bus_id = bus_id

    def __repr__(self):
        return f'<GPUInfo(name={self.name}, physical_gpu_index={self.physical_gpu_index}, bus_id={self.bus_id}, vram_capacity_mib={self.vram_capacity_mib})>'


class GPUInfoSchema(Schema):
    name = fields.String(required=True)
    physical_gpu_index = fields.Integer(required=False, default=None)
    vram_capacity_mib = fields.Integer(required=False, default=None)
    bus_id = fields.String(required=False, default=None)

    @post_load
    def make_gpu_info(self, data, **kwargs):
        return GPUInfo(**data)
