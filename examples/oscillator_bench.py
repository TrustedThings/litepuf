#!/usr/bin/env python3

from migen import *

from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.cores.freqmeter import FreqMeter
from litex.soc.integration.builder import Builder

from litex.build.generic_platform import Subsignal, IOStandard, Pins

from litex_boards.platforms import ecp5_evn
from litex_boards.targets.ecp5_evn import BaseSoC

from litescope import LiteScopeIO, LiteScopeAnalyzer

from metastable import RingOscillator
from metastable.oscillator import MetastableOscillator


class LiteScopeSoC(BaseSoC):
    # csr_map = {
    #     "analyzer": 17
    # }
    # csr_map.update(BaseSoC.csr_map)

    def __init__(self):
        sys_clk_freq = int(50e6) # check

        BaseSoC.__init__(self, sys_clk_freq, x5_clk_freq=int(50e6), # toolchain="trellis",
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            #ident="Litescope example design", ident_version=True,
            with_timer=False
        )

        # bridge
        self.platform.add_extension([
            ("serial", 1,
                Subsignal("rx", Pins("P18"), IOStandard("LVCMOS33")),
                Subsignal("tx", Pins("N20"), IOStandard("LVCMOS33")),
            )
        ])
        bridge = UARTWishboneBridge(self.platform.request("serial", 0), sys_clk_freq, baudrate=115200)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        # Litescope Analyzer
        analyzer_groups = {}

        self.submodules.osc = RingOscillator(
            [
                "X4/Y11/SLICEA",
                "X4/Y11/SLICEB",
                "X4/Y11/SLICEC",
                "X4/Y11/SLICED",
                "X5/Y11/SLICEA",
                "X5/Y11/SLICEB",
                "X5/Y11/SLICEC",
                "X5/Y11/SLICED",
                "X6/Y11/SLICEA",
                "X6/Y11/SLICEB",
                "X6/Y11/SLICEC",
                "X6/Y11/SLICED",
            ])

        self.platform.add_extension([("osc_clk", 0, Pins("G18"), IOStandard("LVCMOS33"))])
        self.comb += self.osc.enable.eq(1)
        self.platform.request("osc_clk", 0).eq(self.osc.ring_out)

        self.submodules.fmeter = FreqMeter(sys_clk_freq, clk=self.osc.ring_out)

        analyzer_groups[0] = [
            self.osc.ring_out
        ]

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups, 512)
        self.add_csr("analyzer")
        

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "test/analyzer.csv")


soc = LiteScopeSoC()
builder = Builder(soc, csr_csv="test/csr.csv", csr_json="test/csr.json")
vns = builder.build(nowidelut=True, ignoreloops=True)

#
# Create csr and analyzer files
#
soc.finalize()
soc.do_exit(vns)
