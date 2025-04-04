from marshmallow import Schema, fields, post_load


class GPUInfo:
    def __init__(self, name: str, vram_capacity_mib: int | None = None, bus_id: str | None = None):
        self.name = name
        self.vram_capacity_mib = vram_capacity_mib
        self.bus_id = bus_id

    def __repr__(self):
        return f'<GPUInfo(name={self.name}, bus_id={self.bus_id}, vram_capacity_mib={self.vram_capacity_mib})>'


class GPUInfoSchema(Schema):
    name = fields.String(required=True)
    vram_capacity_mib = fields.Integer(required=False, default=None)
    bus_id = fields.String(required=False, default=None)

    @post_load
    def make_gpu_info(self, data, **kwargs):
        return GPUInfo(**data)
