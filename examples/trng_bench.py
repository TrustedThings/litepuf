#!/usr/bin/env python3

from os import path
from itertools import cycle, islice, chain, count

from migen import *

from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.integration.builder import Builder

from litex.build.generic_platform import Subsignal, IOStandard, Pins

from litex_boards.platforms import ecp5_evn
from litex_boards.targets.ecp5_evn import BaseSoC

from litescope import LiteScopeIO, LiteScopeAnalyzer

from metastable import RingOscillator
from metastable.oscillator import MetastableOscillator
from metastable.random import RandomLFSR

def slicer():
    slice_iter = cycle("ABCD")
    for i in count(0):
        for _ in range(4):
            yield (i, next(slice_iter))

def ro_placer(num_chains, chain_length):
    for chain in range(num_chains):
        placement = [f"X{4+column}/Y{11+chain}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)]
        print(placement)
        yield placement

class LiteScopeSoC(BaseSoC):
    csr_map = {
        "io":       16,
        "analyzer": 17
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self):
        sys_clk_freq = int(50e6) # check

        BaseSoC.__init__(self, sys_clk_freq, x5_clk_freq=int(50e6), toolchain="trellis", # check
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            # ident="Litescope example design", ident_version=True,
            with_timer=False
        )
        
        # bridge
        bridge = UARTWishboneBridge(self.platform.request("serial"), sys_clk_freq, baudrate=923076)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        self.platform.add_source_dir(path.join(path.dirname(__file__), 'verilog/lattice_ecp5'))
        self.platform.add_source(path.join(path.dirname(__file__), 'verilog/lfsr.v'))
        self.platform.add_source(path.join(path.dirname(__file__), 'verilog/random.v'))

        metastable = Signal(name_override="metastable")
        metastable.attr.add(("keep", 1))
        rand_out = Signal(8, name_override="lfsr_weak")
        
        chain_out = Signal(name_override="chain_out")#, attr=set(["keep", ("noglobal", "1")]))
        chain_out.attr.add(("keep", 1))
        chain_out.attr.add(("noglobal", 1))
        
        self.submodules.ro = RingOscillator(
            [
                "X20/Y20/SLICEA",
                "X20/Y20/SLICEB",
                "X20/Y20/SLICEC",
                "X20/Y20/SLICED",
            ])

        # Litescope IO
        self.submodules.io = LiteScopeIO(8)
        for i in range(7):#8
            try:
                self.comb += self.platform.request("user_led", i).eq(self.io.output[i])
            except:
                pass

        # Litescope Analyzer
        analyzer_groups = {}

        self.specials += [
        Instance("randomized_lfsr_weak",
                    i_clk=self.crg.cd_sys.clk,
                    i_rst=~self.platform.lookup_request("rst_n"),
                    o_out=rand_out,
                    o_metastable=metastable
                    ),
        ]

        oscillators = [RingOscillator(placement) for placement in ro_placer(4, 5)]
        self.submodules.trng = trng = RandomLFSR(oscillators)

        analyzer_groups[0] = [
            rand_out,
            metastable
        ]

        analyzer_groups[1] = [
            trng.word_ready,
            trng.reset,
            trng.word_o,
            trng.metastable,
            trng.oscillators_o,
            trng.counter_rng,
            trng.trng,
        ]

        analyzer_signals = [
            trng.metastable,
        ]

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
            depth=2**20,
            clock_domain="sys",
            csr_csv="test/analyzer.csv")


soc = LiteScopeSoC()
builder = Builder(soc, csr_csv="test/csr.csv", csr_json="test/csr.json")
vns = builder.build(nowidelut=True, ignoreloops=True)

#
# Create csr and analyzer files
#
soc.finalize()

soc.do_exit(vns)
