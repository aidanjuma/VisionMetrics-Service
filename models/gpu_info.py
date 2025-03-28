from marshmallow import Schema, fields, post_load


class GPUInfo:
    def __init__(self, name: str, vram_capacity: int):
        self.name = name
        self.vram_capacity = vram_capacity

    def __repr__(self):
        return f'<GPUInfo(name={self.name}, vram_capacity={self.vram_capacity})>'


class GPUInfoSchema(Schema):
    name = fields.String(required=True)
    vram_capacity = fields.Integer(required=True)

    @post_load
    def make_gpu_info(self, data, **kwargs):
        return GPUInfo(**data)
