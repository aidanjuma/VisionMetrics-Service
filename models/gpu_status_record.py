from marshmallow import Schema, fields, post_load

from models.gpu_info import GPUInfo


class GPUStatusRecord(GPUInfo):
    def __init__(self, name: str, timestamp: str, p_state: str, temperature: int,
                 gpu_utilization: int, memory_utilization: int, clock_sm: int, clock_memory: int, clock_graphics: int,
                 power_usage: int, memory_free_mib: int, memory_used_mib: int, pcie_rx: int, pcie_tx: int,
                 session_id: int | None = None, vram_capacity_mib: int | None = None, bus_id: str | None = None):
        super().__init__(name, vram_capacity_mib, bus_id)
        self.timestamp = timestamp
        self.p_state = p_state  # P0 (max. pwr.) - P12 (min. pwr.)
        self.temperature = temperature  # in deg. C.
        self.gpu_utilization = gpu_utilization  # %
        self.memory_utilization = memory_utilization  # %
        self.clock_sm = clock_sm
        self.clock_memory = clock_memory
        self.clock_graphics = clock_graphics
        self.power_usage = power_usage  # Watts (W)
        self.memory_free_mib = memory_free_mib
        self.memory_used_mib = memory_used_mib
        self.pcie_rx = pcie_rx  # KB/s
        self.pcie_tx = pcie_tx  # KB/s
        self.session_id = session_id  # For DB-tracking purposes.


class GPUStatusRecordSchema(Schema):
    # Inherited:
    name = fields.String(required=True)
    bus_id = fields.String(required=False, default=None)
    vram_capacity_mib = fields.Integer(required=False, default=None)

    # New:
    timestamp = fields.DateTime(required=True)
    p_state = fields.String(required=False, default=None)
    temperature = fields.Integer(required=False, default=None)
    gpu_utilization = fields.Integer(required=False, default=None)
    memory_utilization = fields.Integer(required=False, default=None)
    clock_sm = fields.Integer(required=False, default=None)
    clock_memory = fields.Integer(required=False, default=None)
    clock_graphics = fields.Integer(required=False, default=None)
    power_usage = fields.Integer(required=False, default=None)
    memory_free_mib = fields.Integer(required=False, default=None)
    memory_used_mib = fields.Integer(required=False, default=None)
    pcie_rx = fields.Integer(required=False, default=None)
    pcie_tx = fields.Integer(required=False, default=None)
    session_id = fields.Integer(required=False, default=None)

    @post_load
    def make_gpu_status_record(self, data, **kwargs):
        return GPUStatusRecord(**data)
