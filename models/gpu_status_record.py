from marshmallow import Schema, fields

from models.gpu_info import GPUInfo


class GPUStatusRecord(GPUInfo):
    def __init__(self, name: str, bus_id: str, vram_capacity_mib: int, timestamp: str, p_state: str, temperature: int,
                 gpu_utilization: int, memory_utilization: int, clock_sm: int, clock_memory: int, clock_graphics: int,
                 power_usage: int, memory_free_mib: int, memory_used_mib: int, pcie_rx: int, pcie_tx: int):
        super().__init__(name, bus_id, vram_capacity_mib)
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


class GPUStatusRecordSchema(Schema):
    # Inherited:
    name = fields.String(required=True)
    bus_id = fields.String(required=False, default=None)
    vram_capacity_mib = fields.Integer(required=True)

    # New:
    timestamp = fields.DateTime(required=True)
    p_state = fields.String(required=True)
    temperature = fields.Integer(required=True)
    gpu_utilization = fields.Integer(required=True)
    memory_utilization = fields.Integer(required=True)
    clock_sm = fields.Integer(required=True)
    clock_memory = fields.Integer(required=True)
    clock_graphics = fields.Integer(required=True)
    power_usage = fields.Integer(required=True)
    memory_free_mib = fields.Integer(required=True)
    memory_used_mib = fields.Integer(required=True)
    pcie_rx = fields.Integer(required=True)
    pcie_tx = fields.Integer(required=True)
