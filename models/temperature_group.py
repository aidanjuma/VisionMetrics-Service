from marshmallow import Schema, fields, post_load

from models.temperature_reading import TemperatureReading, TemperatureReadingSchema


class TemperatureGroup:
    def __init__(self, sensor_group: str, readings: [TemperatureReading]):
        self.sensor_group = sensor_group
        self.readings = readings

    def __repr__(self):
        return f'<TemperatureGroup(sensor_group={self.sensor_group}, readings={self.readings})>'


class TemperatureGroupSchema(Schema):
    sensor_group = fields.String(required=True)
    readings = fields.List(fields.Nested(TemperatureReadingSchema), required=True)

    @post_load
    def make_temperature_group(self, data, **kwargs):
        return TemperatureGroup(**data)
