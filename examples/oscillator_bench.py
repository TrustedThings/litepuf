#!/usr/bin/env python3

from itertools import cycle, islice, chain, count

from migen import *
from migen.genlib.io import CRG

from litex.soc.cores.uart import UARTWishboneBridge

from litex.build.generic_platform import Subsignal, IOStandard, Pins

from litex_boards.community.platforms import ecp5_evn
from litex_boards.community.targets.ecp5_evn import BaseSoC

from litescope import LiteScopeIO, LiteScopeAnalyzer

from metastable import RingOscillator, TEROCell
from metastable.oscillator import MetastableOscillator
from metastable.cores import RingOscillatorPUF, TransientEffectRingOscillatorPUF as TEROPUF, SpeedOptimizedHybridOscillatorArbiterPUF as HybridOscillatorArbiterPUF
from metastable.random import RandomLFSR


class LiteScopeSoC(BaseSoC):
    csr_map = {
        "analyzer": 17
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self):
        sys_clk_freq = int(60e6) # check

        BaseSoC.__init__(self, sys_clk_freq, x5_clk_freq=int(50e6), toolchain="trellis", # check
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design", ident_version=True,
            with_timer=False
        )

        # bridge
        self.add_cpu(UARTWishboneBridge(self.platform.request("serial"),
            sys_clk_freq, baudrate=115200))
        self.add_wb_master(self.cpu.wishbone)

        # Litescope Analyzer
        analyzer_groups = {}

        self.submodules.osc = RingOscillator(
            [
                "X20/Y20/SLICEA",
                "X20/Y20/SLICEB",
                "X20/Y20/SLICEC",
                "X20/Y20/SLICED"
            ])

        self.platform.add_extension([("osc_clk", 0, Pins("G18"), IOStandard("LVCMOS33"))])
        self.comb += self.osc.enable.eq(1)
        self.platform.request("osc_clk", 0).eq(self.osc.ring_out)

        analyzer_groups[0] = [
            self.osc.ring_out
        ]

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups, 512)
        

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "test/analyzer.csv")


soc = LiteScopeSoC()
vns = soc.platform.build(soc)

#
# Create csr and analyzer files
#
soc.finalize()
from litex.build.tools import write_to_file
from litex.soc.integration import cpu_interface

csr_json = cpu_interface.get_csr_json(soc.csr_regions, soc.constants, soc.mem_regions)
write_to_file("test/csr.json", csr_json)
soc.do_exit(vns)
