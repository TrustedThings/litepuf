# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg


class Chain(Module):
    """Inverter chain

    NAND-NOT-...-NOT
    """
    def __init__(self, enable, length, chain_in=None, chain_out=None):
        if chain_in is None:
            self.chain_in = chain_in = Signal()
        if chain_out is None:
            chain_out = Signal()
        self.chain_out = chain_out

        buffers_in = Signal(length)
        buffers_out = Signal(length)
        
        self.comb += buffers_in.eq(Cat(chain_in, buffers_out[0:-1]))
        self.comb += chain_out.eq(buffers_out[-1])

        chain_iter = enumerate(zip(buffers_in, buffers_out))
        
        i, (buf_in, buf_out) = next(chain_iter)
        initializer = Instance("SB_LUT4",
                                p_LUT_INIT=0b0111, # NAND
                                i_I0=buf_in,
                                i_I1=enable,
                                i_I2=0,
                                i_I3=0,
                                o_O=buf_out)
        self.specials += initializer

        for i, (buf_in, buf_out) in chain_iter:
            inverter = Instance("SB_LUT4",
                                    # a_BEL=f"X2/Y5/lc{i}"
                                    p_LUT_INIT=0b01,
                                    i_I0=buf_in,
                                    i_I1=0,
                                    i_I2=0,
                                    i_I3=0,
                                    o_O=buf_out)
            #inverter.synthesis_directive = "helloworld"
            #inverter.attrs["BEL"] = f"X2/Y5/lc{i}"
            self.specials += inverter


class RingOscillator(Module):
    """Ring oscillator
    """
    def __init__(self, enable, length, ring_out=None):
        if ring_out is None:
            self.ring_out = ring_out = Signal()
        self.submodules.chain = chain = Chain(enable, length, ring_out, ring_out)


class ROSet(Module):
    def __init__(self, enable, select, oscillators):
        self.counter = counter = Signal(24)
        
        self.submodules += oscillators
        mux = Array(ro.ring_out for ro in oscillators)

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain

        #self.comb += cd_chain.clk.eq(oscillators[0].ring_out)
        self.comb += cd_chain.clk.eq(mux[select])
        #self.sync.chain += counter.eq(counter + 1)
        resetn = Signal()
        self.sync.chain += [
            If(enable,
                If(resetn,
                    counter.eq(C(1, len(counter))),
                    resetn.eq(0)
                ).Else(
                    counter.eq(counter + 1)
                )
            ).Else(
                resetn.eq(1)
            )
        ]
