# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

from .oscillator import RingOscillator, ROSet


class RingOscillator2(Module, AutoCSR):
    def __init__(self, pads, clock_domain="sys"):
        counter  = Signal(20)
        enable = Signal()

        self._enable = CSRStorage(reset=0)
        self._counter = CSRStorage(16, reset=0)

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain
        #self.clock_domains.cd_sys = ClockDomain()
        
        # Resynchronize to clock_domain ------------------------------------------------------------
        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            #MultiReg(self._counter.storage, counter, clock_domain),
        ]

        chain_in = Signal()
        chain_out = Signal()
        
        buffers_in = Signal(99)
        buffers_out = Signal(99)
        
        self.comb += buffers_in.eq(Cat(buffers_out[-1:], buffers_out[0:-1]))

        chain_iter = zip(buffers_in, buffers_out)
        
        chain_in, buf_out = next(chain_iter)
        initializer = Instance("SB_LUT4",
                                p_LUT_INIT=0b0111, # NAND
                                i_I0=chain_in,
                                i_I1=enable,
                                i_I2=0,
                                i_I3=0,
                                o_O=buf_out)
        self.specials += initializer

        for buf_in, buf_out in chain_iter:
            inverter = Instance("SB_LUT4",
                                    p_LUT_INIT=0b01,
                                    i_I0=buf_in,
                                    i_I1=0,
                                    i_I2=0,
                                    i_I3=0,
                                    o_O=buf_out)
            #inverter.attrs["BEL"] = f"X2/Y5/lc{i}"
            self.specials += inverter
        
        #m.d.comb += cd_chain.clk.eq(chain_out)
        self.comb += cd_chain.clk.eq(buffers_out[-1])

        self.sync.chain += counter.eq(counter + 1)
        self.comb += pads.out.eq(counter[-1])


class RingClock(Module, AutoCSR):
    def __init__(self, pads, length, clock_domain="sys"):
        counter  = Signal(24)
        enable = Signal()

        self._enable = CSRStorage(reset=0)

        # Resynchronize to clock_domain ------------------------------------------------------------
        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            #MultiReg(self._counter.storage, counter, clock_domain),
        ]

        # chain_out = Signal()
        # self.submodules.ring = RingOscillator(enable, length, chain_out)

        self.submodules.ring = ring = RingOscillator(enable, length)
        chain_out = ring.ring_out

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain

        self.comb += cd_chain.clk.eq(chain_out)
        self.sync.chain += counter.eq(counter + 1)
        self.comb += pads.out.eq(counter[-1])


class RingOscillatorPUF(Module, AutoCSR):
    def __init__(self, enable, pads, oscillators, clock_domain="sys"):
        self.bit_value = comparator = Signal()

        self._enable = CSRStorage(reset=0)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(reset=0)

        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(comparator, self._bit_value.status, clock_domain),
        ]

        ro_sets = (
            ROSet(enable, select0.storage, oscillators[0]),
            ROSet(enable, select1.storage, oscillators[1]),
        )
        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]

        self.comb += comparator.eq(ro_sets[0].counter < ro_sets[1].counter)
        self.comb += pads.out.eq(ro_sets[0].counter[-1])


class TransientEffectRingOscillatorPUF(Module, AutoCSR):
    def __init__(self, enable, pads, cell_sets, clock_domain="sys"):
        self.bit_value = comparator = Signal(16)

        self._enable = CSRStorage(reset=0)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(16, reset=0)

        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(comparator, self._bit_value.status, clock_domain),
        ]

        ro_sets = (
            ROSet(enable, select0.storage, cell_sets[0], counter=Signal(16)),
            ROSet(enable, select1.storage, cell_sets[1], counter=Signal(16)),
        )
        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]

        self.comb += comparator.eq(ro_sets[0].counter - ro_sets[1].counter)
        self.comb += pads.out.eq(ro_sets[0].counter[-1])


class PowerOptimizedHybridOscillatorArbiterPUF(Module, AutoCSR):
    def __init__(self, enable, pads, oscillators, clock_domain="sys"):
        self.bit_value = bit_value = Signal()

        self._enable = CSRStorage(reset=0)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(reset=0)

        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(bit_value, self._bit_value.status, clock_domain),
        ]

        ro_sets = (
            ROSet(enable, select0.storage, oscillators[0]),
            ROSet(enable, select1.storage, oscillators[1]),
        )

        d_flipflop = Instance("SB_DFF",
            i_D=ro_sets[0].ring_out,
            i_C=ro_sets[1].ring_out,
            o_Q=bit_value)
        self.specials += d_flipflop

        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]


class SpeedOptimizedHybridOscillatorArbiterPUF(Module, AutoCSR):
    def __init__(self, enable, pads, oscillators, clock_domain="sys"):
        self.key = key = Signal(len(oscillators[0]))

        self._enable = CSRStorage(reset=0)
        self._key = CSRStatus(len(key), reset=0)

        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(key, self._key.status, clock_domain),
        ]

        for i, ro in enumerate(zip(*oscillators)):
            d_flipflop = Instance("SB_DFF",
                i_D=ro[0].ring_out,
                i_C=ro[1].ring_out,
                o_Q=key[i])
            self.specials += d_flipflop
            self.submodules += ro


class Muxer(Module, AutoCSR):
    def __init__(self, pads, length):
        mux = Array(C(i, 16) for i in reversed(range(8)))

        self._cell_select = select = CSRStorage(8)
        self._cell_counter = counter = CSRStatus(16)

        self.sync += counter.status.eq(mux[select.storage])

        self.submodules += RingClock(pads, length)
