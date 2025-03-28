from marshmallow import Schema, fields, post_load


class TemperatureReading:
    def __init__(self, label: str, current: float, high: float = None, critical: float = None):
        self.label = label
        self.current = current
        self.high = high
        self.critical = critical

    def __repr__(self):
        return (
            f'<TemperatureReading(label={self.label}, current={self.current}°C, '
            f'high={self.high}°C, critical={self.critical}°C)>'
        )


class TemperatureReadingSchema(Schema):
    label = fields.String(required=True)
    current = fields.Float(required=True)
    high = fields.Float(allow_none=True)
    critical = fields.Float(allow_none=True)

    @post_load
    def make_temperature_reading(self, data, **kwargs):
        return TemperatureReading(**data)
