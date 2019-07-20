# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg


class Chain(Module):
    """Inverter chain

    NAND-NOT-...-NOT
    """
    def __init__(self, enable, placement, chain_in=None, chain_out=None, initializer_LUT=0b0111):
        if chain_in is None:
            self.chain_in = chain_in = Signal()
        if chain_out is None:
            chain_out = Signal()
        self.chain_out = chain_out

        buffers_in = Signal(len(placement))
        buffers_out = Signal(len(placement))
        
        self.comb += buffers_in.eq(Cat(chain_in, buffers_out[0:-1]))
        self.comb += chain_out.eq(buffers_out[-1])

        bel = lambda pos: {"a_BEL": pos} if pos else None
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
                                    # a_BEL=f"X2/Y5/lc{i}"
                                    p_LUT_INIT=0b01,
                                    i_I0=buf_in,
                                    i_I1=0,
                                    i_I2=0,
                                    i_I3=0,
                                    o_O=buf_out,
                                    **attrs)
            #inverter.synthesis_directive = "helloworld"
            self.specials += inverter


class RingOscillator(Module):
    """Ring oscillator
    """
    def __init__(self, enable, placement, ring_out=None):
        if ring_out is None:
            self.ring_out = ring_out = Signal()
        self.submodules.chain = chain = Chain(enable, placement, ring_out, ring_out)


class ROSet(Module):
    def __init__(self, enable, select, oscillators, counter=None):
        if counter is None:
            counter = Signal(24)
        self.counter = counter
        
        self.submodules += oscillators
        mux = Array(ro.ring_out for ro in oscillators)

        cd_chain = ClockDomain(reset_less=True)
        self.clock_domains += cd_chain

        #self.comb += cd_chain.clk.eq(oscillators[0].ring_out)
        self.comb += cd_chain.clk.eq(mux[select])
        self.submodules.counter_fsm = ClockDomainsRenamer("chain")(FSM(reset_state="OSCILLATING"))
        self.counter_fsm.act("IDLE",
            If(enable,
                NextValue(counter, 1),
                NextState("OSCILLATING")
            )
        )
        self.counter_fsm.act("OSCILLATING",
            If(enable,
                NextValue(counter, counter + 1)
            ).Else(
                NextState("IDLE")
            )
        )
