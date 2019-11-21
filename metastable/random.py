# This file is Copyright (c) 2019 Arnaud Durand <arnaud.durand@unifr.ch>
# License: BSD

from functools import reduce
from operator import xor, or_

from migen import *

class LFSR(Module):
    def __init__(self, width, shiftreg_init, taps):
        self.reset = Signal()
        self.random = Signal()
        self.shiftreg = Signal(width)
        feedback = Signal()
        taps = Constant(taps)
        #self.initialized = Signal()

        self.comb += feedback.eq(self.random ^ reduce(xor, self.shiftreg & taps))

        self.sync += \
            If(self.reset,
                self.shiftreg.eq(shiftreg_init)
            ).Else(
                self.shiftreg.eq(Cat(self.shiftreg[1:], feedback))
            )


class RandomLFSR(Module):
    def __init__(self, oscillator, shiftreg_init=0b1010_1100_1110_0001, taps=0b0000_0000_0010_1101):
        self.reset = Signal()
        self.word_ready = Signal()
        shiftreg_width = 16
        bits_remaining = Signal(shiftreg_width-1)
        #previous_bit_ready = Signal()

        self.sync += \
            If(self.reset | self.word_ready, # TODO: logical OR
                bits_remaining.eq(16)
            ), bits_remaining.eq(bits_remaining-1)#.Else(
            #     If(~previous_bit_ready & bit_ready, # TODO: logical AND w/bit_ready
            #         bits_remaining.eq(bits_remaining-1)
            # )), previous_bit_rdy.eq(bit_ready)
        self.comb += \
            self.word_ready.eq(bits_remaining==0)
            #words_ready.eq(~reduce(or_, bits_remaining))
            # If(bits_remaining,
            #     word_ready.eq(False)
            # ).Else(
            #     word_ready.eq(True)
            # )
        
        #debias = Debias()
        lsfr = LFSR(shiftreg_width, shiftreg_init, taps)
        #lsfr = ClockDomainsRenamer("chain")lsfr
        self.submodules += oscillator, lsfr

        self.comb += [
            lsfr.random.eq(oscillator.o),
            lsfr.reset.eq(self.reset)]
        
        self.shiftreg = lsfr.shiftreg
