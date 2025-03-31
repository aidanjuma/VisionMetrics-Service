from marshmallow import Schema, fields, post_load


class GPUInfo:
    def __init__(self, name: str, bus_id: str, vram_capacity_mib: int):
        self.name = name
        self.bus_id = bus_id
        self.vram_capacity_mib = vram_capacity_mib

    def __repr__(self):
        return f'<GPUInfo(name={self.name}, bus_id={self.bus_id}, vram_capacity_mib={self.vram_capacity_mib})>'


class GPUInfoSchema(Schema):
    name = fields.String(required=True)
    bus_id = fields.String(required=False, default=None)
    vram_capacity_mib = fields.Integer(required=True)

    @post_load
    def make_gpu_info(self, data, **kwargs):
        return GPUInfo(**data)
