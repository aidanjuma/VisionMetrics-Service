from marshmallow import Schema, fields, post_load


class CPUInfo:
    def __init__(self, name: str, physical_cores: int, total_cores: int, min_frequency: float, max_frequency: float, ):
        self.name = name
        self.physical_cores = physical_cores
        self.total_cores = total_cores
        self.min_frequency = min_frequency
        self.max_frequency = max_frequency

    def __repr__(self):
        return (
            f'<CPUInfo(name={self.name},physical_cores={self.physical_cores}, total_cores={self.total_cores}, '
            f'min_frequency={self.min_frequency:.2f}MHz), max_frequency={self.max_frequency:.2f}MHz>'
        )


class CPUInfoSchema(Schema):
    name = fields.Str(required=True)
    physical_cores = fields.Integer(required=True)
    total_cores = fields.Integer(required=True)
    min_frequency = fields.Float(required=True)
    max_frequency = fields.Float(required=True)

    @post_load
    def make_cpu_info(self, data, **kwargs):
        return CPUInfo(**data)
