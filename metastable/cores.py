# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *

from .oscillator import RingOscillator, ROSet
from . import PUFType


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


class PulseComparator(Module):
    def __init__(self):
        self.reset = Signal()
        self.pulse0 = Signal()
        self.pulse1 = Signal()
        self.select = Signal()
        self.ready = Signal()

        q0 = Signal()
        q1 = Signal()

        d_flipflops = (
            Instance("FD1S3DX",
                i_D=q0|~q1,
                i_CK=self.pulse0,
                i_CD=self.reset,
                o_Q=q0),
            Instance("FD1S3DX",
                i_D=~q0|q1,
                i_CK=self.pulse1,
                i_CD=self.reset,
                o_Q=q1)
        )
        self.specials += d_flipflops

        self.comb += [
            self.select.eq(q1), #q0
            self.ready.eq(q0|q1)
        ]


class ClockGenerator(Module, AutoCSR):
    def __init__(self, pads, length, counter=None, clock_domain="sys"):
        if counter is None:
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
        placement = [None] * length # no explicit placement
        self.submodules.ring = ring = RingOscillator(enable, placement)
        chain_out = ring.ring_out

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain

        self.comb += cd_chain.clk.eq(chain_out)
        self.sync.chain += counter.eq(counter + 1)
        self.comb += pads.out.eq(counter[-1])


class RingOscillatorPUF(Module, AutoCSR):

    puf_type = PUFType.RO

    def __init__(self, oscillators, clock_domain="sys"):
        self.bit_value = comparator = Signal()
        self.reset = Signal()

        self._reset = CSRStorage(reset=1)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(reset=0)

        ro_sets = (
            ROSet(oscillators[0]),
            ROSet(oscillators[1]),
        )
        self.comb += [
            ro_sets[0].reset.eq(self.reset),
            ro_sets[1].reset.eq(self.reset)
        ]

        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]

        self.specials += [
            MultiReg(self._reset.storage, self.reset, clock_domain),
            MultiReg(select0.storage, ro_sets[0].select, clock_domain),
            MultiReg(select1.storage, ro_sets[1].select, clock_domain),
            MultiReg(comparator, self._bit_value.status, clock_domain),
        ]

        ro_sets[0].add_counter(20)
        ro_sets[1].add_counter(20)
        #self.comb += comparator.eq(ro_sets[0].counter < ro_sets[1].counter)

        self.submodules.pulse_comp = PulseComparator()
        self.comb += [
            self.pulse_comp.reset.eq(self.reset),
            self.pulse_comp.pulse0.eq(ro_sets[0].counter[-1]),
            self.pulse_comp.pulse1.eq(ro_sets[1].counter[-1])
        ]
        self.comb += comparator.eq(self.pulse_comp.select)


class TransientEffectRingOscillatorPUF(Module, AutoCSR):

    puf_type = PUFType.TERO

    def __init__(self, cell_sets, clock_domain="sys"):
        self.bit_value = comparator = Signal(32)
        self.reset = Signal()

        self._reset = CSRStorage(reset=1)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(32, reset=0)

        ro_sets = (
            ROSet(cell_sets[0]),
            ROSet(cell_sets[1]),
        )
        self.comb += [
            ro_sets[0].reset.eq(self.reset),
            ro_sets[1].reset.eq(self.reset)
        ]

        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]

        self.specials += [
            MultiReg(self._reset.storage, self.reset, clock_domain),
            MultiReg(select0.storage, ro_sets[0].select, clock_domain),
            MultiReg(select1.storage, ro_sets[1].select, clock_domain),
            MultiReg(comparator, self._bit_value.status, clock_domain),
        ]

        ro_sets[0].add_counter(32)
        ro_sets[1].add_counter(32)

        timer = WaitTimer(180) # wait 180 clock cycles at sys freq (50 Hz)
        latch = Signal()
        self.submodules += timer
        self.comb += timer.wait.eq(~self.reset)
        self.sync += [
            latch.eq(timer.done),
            If(timer.done & ~latch,
                comparator.eq(ro_sets[0].counter - ro_sets[1].counter)
            )
        ]


class PowerOptimizedHybridOscillatorArbiterPUF(Module, AutoCSR):

    puf_type = PUFType.HYBRID

    def __init__(self, oscillators, clock_domain="sys"):
        self.bit_value = Signal()
        self.reset = Signal()

        self._reset = CSRStorage(reset=1)
        self._cell0_select = select0 = CSRStorage(8)
        self._cell1_select = select1 = CSRStorage(8)
        self._bit_value = CSRStatus(reset=0)

        ro_sets = (
            ROSet(oscillators[0]),
            ROSet(oscillators[1]),
        )
        self.comb += [
            ro_sets[0].reset.eq(self.reset),
            ro_sets[1].reset.eq(self.reset)
        ]

        #self.submodules += ro_sets
        self.submodules.ro_set0 = ro_sets[0]
        self.submodules.ro_set1 = ro_sets[1]

        self.specials += [
            MultiReg(self._reset.storage, self.reset, clock_domain),
            MultiReg(select0.storage, ro_sets[0].select, clock_domain),
            MultiReg(select1.storage, ro_sets[1].select, clock_domain),
            MultiReg(self.bit_value, self._bit_value.status, clock_domain),
        ]

        self.ff_o = Signal()
        d_flipflop = Instance("FD1S3AX",
            i_D=ro_sets[0].ring_out,
            i_CK=ro_sets[1].ring_out,
            o_Q=self.ff_o)
        self.specials += d_flipflop
    
        timer = WaitTimer(180) # wait 180 clock cycles at sys freq (50 Hz)
        latch = Signal()
        self.submodules += timer
        self.comb += timer.wait.eq(~self.reset)
        self.sync += [
            latch.eq(timer.done),
            If(timer.done & ~latch,
                self.bit_value.eq(self.ff_o)
            )
        ]


class SpeedOptimizedHybridOscillatorArbiterPUF(Module, AutoCSR):
    def __init__(self, enable, oscillators, clock_domain="sys"):
        self.key = key = Signal(len(oscillators[0]))

        self._enable = CSRStorage(reset=0)
        self._key = CSRStatus(len(key), reset=0)

        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(key, self._key.status, clock_domain),
        ]

        for i, ro in enumerate(zip(*oscillators)):
            d_flipflop = Instance("FD1S3AX",
                i_D=ro[0].ring_out,
                i_CK=ro[1].ring_out,
                o_Q=key[i])
            self.specials += d_flipflop
            self.submodules += ro


class Muxer(Module, AutoCSR):
    def __init__(self, pads, length):
        mux = Array(C(i, 16) for i in reversed(range(8)))

        self._cell_select = select = CSRStorage(8)
        self._cell_counter = counter = CSRStatus(16)

        self.sync += counter.status.eq(mux[select.storage])

        self.submodules += ClockGenerator(pads, length)
