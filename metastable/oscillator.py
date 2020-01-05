# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg


platform = "trellis"

def LUT4(init, a, b, c, d, z, **attrs):
    if platform == "icestorm":
        return Instance("SB_LUT4",
            p_LUT_INIT=init,
            i_I0=a,
            i_I1=b,
            i_I2=c,
            i_I3=d,
            o_O=z,
            **attrs)
    else:
        return Instance("LUT4",
            p_INIT=init,
            i_A=a,
            i_B=b,
            i_C=c,
            i_D=d,
            o_Z=z,
            **attrs)

class IceStormChain(Module):
    """Inverter chain

    NAND-NOT-...-NOT
    """
    def __init__(self, enable, placement, chain_in=None, chain_out=None):
        if chain_in is None:
            self.chain_in = chain_in = Signal()
        if chain_out is None:
            chain_out = Signal()
        self.chain_out = chain_out

        buffers_in = Signal(len(placement))
        buffers_out = Signal(len(placement))
        
        self.comb += buffers_in.eq(Cat(chain_in, buffers_out[0:-1]))
        self.comb += chain_out.eq(buffers_out[-1])

        bel = lambda pos: {"a_BEL": pos} if pos else {}
        chain_iter = zip(map(bel, placement), zip(buffers_in, buffers_out))
        
        attrs, (buf_in, buf_out) = next(chain_iter)
        initializer = Instance("SB_LUT4",
                                p_LUT_INIT=0b0111, # NAND
                                i_I0=buf_in,
                                i_I1=enable,
                                i_I2=0,
                                i_I3=0,
                                o_O=buf_out,
                                **attrs)
        self.specials += initializer

        for attrs, (buf_in, buf_out) in chain_iter:
            inverter = Instance("SB_LUT4",
                                    p_LUT_INIT=0b01,
                                    i_I0=buf_in,
                                    i_I1=0,
                                    i_I2=0,
                                    i_I3=0,
                                    o_O=buf_out,
                                    **attrs)
            #inverter.synthesis_directive = "helloworld"
            self.specials += inverter


class TrellisChain(Module):
    """Inverter chain

    NAND-delay-...-delay
    """
    def __init__(self, placement):
        self.enable = Signal()
        self.chain_in = Signal()
        self.chain_out = Signal(attr={("noglobal", 1)})
        #self.chain_out.attr.add("keep") # check

        buffers_in = Signal(len(placement))
        buffers_out = Signal(len(placement))
        
        self.comb += buffers_in.eq(Cat(self.chain_in, buffers_out[0:-1]))
        self.comb += self.chain_out.eq(buffers_out[-1])

        bel = lambda pos: ("BEL", pos) if pos else ()
        chain_iter = zip(map(bel, placement), zip(buffers_in, buffers_out))

        attr, (buf_in, buf_out) = next(chain_iter)
        initializer = Instance("TRELLIS_SLICE",
                                p_LUT0_INITVAL=0x0007, # NAND
                                i_A0=buf_in,
                                i_B0=self.enable,
                                i_C0=0,
                                i_D0=0,
                                o_F0=buf_out,
                                attr=[attr])
        self.specials += initializer

        for attr, (buf_in, buf_out) in chain_iter:
            delay = Instance("TRELLIS_SLICE",
                                    p_LUT0_INITVAL=0x0002, # delay
                                    i_A0=buf_in,
                                    i_B0=0,
                                    i_C0=0,
                                    i_D0=0,
                                    o_F0=buf_out,
                                    attr=[attr])
            self.specials += delay


class RingOscillator(Module):
    """Ring oscillator
    """
    chain_cls = TrellisChain

    def __init__(self, placement):
        self.enable = Signal()
        self.ring_out = Signal()
        self.submodules.chain = chain = self.chain_cls(placement)

        self.comb += [
            self.chain.enable.eq(self.enable),
            self.chain.chain_in.eq(self.chain.chain_out),
            self.ring_out.eq(self.chain.chain_out)
        ]


class MetastableOscillator(Module):
    def __init__(self, r0, r1, r2, r3, destabilizer_init=0b1010_1100_1110_0001):
        self.submodules += r0, r1, r2, r3
        self.o = Signal()

        destabilizer = Instance("TRELLIS_SLICE",
                                p_LUT0_INITVAL=destabilizer_init,
                                i_A0=r0.ring_out,
                                i_B0=r1.ring_out,
                                i_C0=r2.ring_out,
                                i_D0=r3.ring_out,
                                o_F0=self.o)
        destabilizer.attr.add("keep")
        self.specials += destabilizer


class TEROCell(Module):
    chain_cls = TrellisChain

    def __init__(self, placement):
        self.enable = Signal()
        self.ring_out = Signal()
        self.submodules.chain1 = self.chain_cls(placement[0])
        self.submodules.chain2 = self.chain_cls(placement[1])

        self.comb += [
            self.chain1.enable.eq(self.enable),
            self.chain2.enable.eq(self.enable),
            self.chain2.chain_in.eq(self.chain1.chain_out),
            self.chain1.chain_in.eq(self.chain2.chain_out),
            self.ring_out.eq(self.chain1.chain_out)
        ]


class ROSet(Module):
    def __init__(self, oscillators):
        self.reset = Signal()
        self.select = Signal(len(oscillators))

        self.submodules += oscillators
        self.comb += [ro.enable.eq(~self.reset) for ro in oscillators] # check
        mux = Array(ro.ring_out for ro in oscillators)

        self.ring_out = Signal()
        self.comb += self.ring_out.eq(mux[self.select])

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain

        #self.comb += cd_chain.clk.eq(oscillators[0].ring_out)
        self.comb += cd_chain.clk.eq(mux[self.select])

    def add_counter(self, width):
        self.counter = Signal(width)

        # self.sync.chain += self.counter.eq(self.counter + 1)
        self.sync.chain += \
            If(self.reset,
                self.counter.eq(0)
            ).Else(
                self.counter.eq(self.counter + 1)
            )

    def add_counter_fsm(self):
        self.counter = Signal(width)

        self.submodules.counter_fsm = ClockDomainsRenamer("chain")(FSM(reset_state="OSCILLATING"))
        self.counter_fsm.act("IDLE",
            If(~self.reset,
                NextValue(self.counter, 1),
                NextState("OSCILLATING")
            )
        )
        self.counter_fsm.act("OSCILLATING",
            If(~self.reset,
                NextValue(self.counter, self.counter + 1)
            ).Else(
                NextState("IDLE")
            )
        )
