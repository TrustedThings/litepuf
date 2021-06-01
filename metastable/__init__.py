from enum import Enum, auto

from .oscillator import RingOscillator, TEROCell, ROSet

class PUFType(Enum):
    RO = auto()
    TERO = auto()
    HYBRID = auto()

    def __str__(self):
        return self.name
