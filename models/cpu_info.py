from marshmallow import Schema, fields, post_load


class CPUInfo:
    def __init__(self, physical_cores: int, total_cores: int, max_frequency: float, min_frequency: float):
        self.physical_cores = physical_cores
        self.total_cores = total_cores
        self.max_frequency = max_frequency
        self.min_frequency = min_frequency

    def __repr__(self):
        return (
            f'<CPUInfo(physical_cores={self.physical_cores}, total_cores={self.total_cores}, '
            f'max_frequency={self.max_frequency:.2f}MHz, min_frequency={self.min_frequency:.2f}MHz)>'
        )


class CPUInfoSchema(Schema):
    physical_cores = fields.Integer(required=True)
    total_cores = fields.Integer(required=True)
    max_frequency = fields.Float(required=True)
    min_frequency = fields.Float(required=True)

    @post_load
    def make_cpu_info(self, data, **kwargs):
        return CPUInfo(**data)
