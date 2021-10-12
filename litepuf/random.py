# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from functools import reduce
from itertools import product
from operator import xor, or_

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

from .oscillator import MetastableOscillator

# see https://www.wolframalpha.com/input/?i=truth+table+p+xor+q+xor+r+xor+s
def xor_lut(n):
    truth_table = product([False, True], repeat=n)
    predicates = [reduce(xor, o) for o in truth_table]
    return sum(v<<i for i, v in enumerate(reversed(predicates)))


class LFSR(Module):
    def __init__(self, width, shiftreg_init, taps, clock_domain="rng"):
        self.reset = Signal()
        self.i = Signal()
        self.shiftreg = Signal(width)
        feedback = Signal()
        taps = Constant(taps)
        #self.initialized = Signal()

        self.comb += feedback.eq(self.i ^ reduce(xor, self.shiftreg & taps))

        self.sampling_clk = ClockSignal(clock_domain)
        sync = getattr(self.sync, clock_domain)
        sync += \
            If(self.reset,
                self.shiftreg.eq(shiftreg_init)
            ).Else(
                self.shiftreg.eq(Cat(self.shiftreg[1:], feedback))
            )


class XORTree(Module):
    def __init__(self, n_inputs):
        assert(n_inputs == 4)
        self.i = Signal(n_inputs)
        self.o = Signal()
        initializer = Instance("TRELLIS_SLICE",
                        p_LUT0_INITVAL=xor_lut(n_inputs), # truth table A xor B xor C xor D
                        i_A0=self.i[0],
                        i_B0=self.i[1],
                        i_C0=self.i[2],
                        i_D0=self.i[3],
                        o_F0=self.o)


class Sampler(Module):
    def __init__(self, clock_domain="rng_sampling"):
        self.i = Signal()
        self.o = Signal()
        self.sampling_clk = ClockSignal(clock_domain)

        sync = getattr(self.sync, clock_domain)
        sync += self.o.eq(self.i)


class RandomLFSR(Module, AutoCSR):
    def __init__(self, oscillators, shiftreg_init=0b0110_1011_1110_0100_1000_0101_0110_1100, taps=0b0000_0000_0000_0000_0000_0000_1100_0101, clock_domain="sys"):
        self.reset = Signal()
        self.metastable = Signal()
        shiftreg_width = 32
        decimation = 1024
        self.word_o = Signal(shiftreg_width)
        self.word_ready = Signal()
        
        bits_remaining = Signal(max=shiftreg_width*decimation)

        self._update_value = CSRStorage(1)
        self._ready = CSRStatus()
        self._random_word = CSRStatus(32)
        
        #sampler = Sampler()
        #sampling_interval = 1024
        #timer  = WaitTimer(int(sampling_interval))
        #debias = Debias()
        lfsr = LFSR(shiftreg_width, shiftreg_init, taps)

        self.oscillators_o = oscillators_o = Signal(len(oscillators))
        for i, o in enumerate(oscillators):
            self.comb += oscillators_o[i].eq(o.ring_out) # foo.eq(Cat(0, 0, bar, 0, baz, 1)),
            self.comb += o.enable.eq(~self.reset)
        self.comb += [
            self.metastable.eq(reduce(xor, oscillators_o)),
            lfsr.i.eq(self.metastable),
            lfsr.reset.eq(self.reset)
        ]

        #cd_chain = ClockDomain(reset_less=True)
        #lsfr = ClockDomainsRenamer("chain")lsfr
        
        cd_rng = ClockDomain("rng", reset_less=True)
        self.clock_domains += cd_rng

        prescaler_clk_counter = Signal(2)
        self.sync += prescaler_clk_counter.eq(prescaler_clk_counter + 1)
        self.sync += cd_rng.clk.eq(prescaler_clk_counter[-1])

        self.counter_rng = counter = Signal(8)
        self.sync.rng += counter.eq(counter + 1)

        self.specials += [
            MultiReg(self.word_ready, self._ready.status, clock_domain),
            MultiReg(self.word_o, self._random_word.status, clock_domain),
        ]

        self.trng = Signal()
        self.sync.rng += self.trng.eq(self.metastable)
        self.comb += lfsr.i.eq(self.trng)
        self.comb += self.word_o.eq(lfsr.shiftreg)

        self.submodules += oscillators
        self.submodules += lfsr, # sampler, debias

        fsm = FSM(reset_state="INIT")
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(self._update_value.re)

        fsm.act("INIT",
            NextValue(bits_remaining, (shiftreg_width * decimation) - 1),
            NextState("EXTRACT"),
        )
        fsm.act("EXTRACT",
            NextValue(bits_remaining, bits_remaining - 1),
            If(bits_remaining == 0,
                NextState("READY"),
            )
        )
        fsm.act("READY",
            self.word_ready.eq(1),
            # TODO: disable oscillators to save power
        )
