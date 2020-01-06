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

def tero_placer(num_cells, chain_length):
    for cell in range(num_cells):
        yield (
            [f"X{2+column}/Y{2+cell}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)],
            [f"X{4+column}/Y{2+cell}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)],
        )


class LiteScopeSoC(BaseSoC):
    csr_map = {
        "ropuf":  7,
        "teropuf":  8,
        "hybridpuf":  9,
        "io":       16,
        "analyzer": 17
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self):
        sys_clk_freq = int(60e6) # check

        BaseSoC.__init__(self, sys_clk_freq, x5_clk_freq=50e6, toolchain="trellis", # check
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            ident="Litescope example design", ident_version=True,
            with_timer=False
        )

        # bridge
        bridge = UARTWishboneBridge(self.platform.request("serial"), sys_clk_freq, baudrate=115200)
        self.submodules.bridge = bridge
        self.add_wb_master(bridge.wishbone)

        # Litescope IO
        self.submodules.io = LiteScopeIO(8)
        for i in range(7):#8
            try:
                self.comb += self.platform.request("user_led", i).eq(self.io.output[i])
            except:
                pass

        # Litescope Analyzer
        analyzer_groups = {}

        # counter group
        counter = Signal(16, name_override="counter")
        zero = Signal(name_override="zero")
        self.sync += counter.eq(counter + 1)
        self.comb += zero.eq(counter == 0)

        puf_reset = Signal(name_override="puf_reset")

        # oscillators1 = []
        # oscillators2 = []
        # p_iter = ro_placer(10, 8)
        # for placement in p_iter:
        #     oscillators1.append(RingOscillator(list(placement)))
        #     oscillators2.append(RingOscillator(list(next(p_iter))))
        # self.submodules.ropuf = puf = RingOscillatorPUF((oscillators1, oscillators2))
        # self.comb += puf.reset.eq(puf_reset)

        oscillators1 = []
        oscillators2 = []
        p_iter = tero_placer(8, 7)
        for placement in p_iter:
            oscillators1.append(TEROCell(list(placement)))
            oscillators2.append(TEROCell(list(next(p_iter))))
        self.submodules.teropuf = puf = TEROPUF((oscillators1, oscillators2))
        self.comb += puf_reset.eq(puf.reset)

        # hybridpuf_enable = puf_enable = Signal(reset=0)
        # oscillators1 = []
        # oscillators2 = []
        # p_iter = ro_placer(8, 7)
        # for placement in p_iter:
        #     oscillators1.append(RingOscillator(hybridpuf_enable, list(placement)))
        #     oscillators2.append(RingOscillator(hybridpuf_enable, list(next(p_iter))))
        # self.submodules.hybridpuf = puf = HybridOscillatorArbiterPUF(hybridpuf_enable, (oscillators1, oscillators2))

        # puf group
        analyzer_groups[0] = [
            puf.bit_value,
            puf_reset,
            puf.ro_set0.counter,
            puf.ro_set1.counter,
            puf.ro_set0.ring_out,
            puf.ro_set1.ring_out,
            # puf.pulse_comp.select,
            # puf.pulse_comp.ready
        ]
        if hasattr(puf, "_cell0_select"):
           analyzer_groups[0].append(puf._cell0_select.storage) 
        if hasattr(puf, "_cell1_select"):
           analyzer_groups[0].append(puf._cell1_select.storage)

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

csr_csv = cpu_interface.get_csr_csv(soc.csr_regions, soc.constants, soc.mem_regions)
csr_json = cpu_interface.get_csr_json(soc.csr_regions, soc.constants, soc.mem_regions)
#csr_sr = cpu_interface.get_csr_sigrok(csr_regions, csr_constants)
write_to_file("test/csr.csv", csr_csv)
write_to_file("test/csr.json", csr_json)
soc.do_exit(vns)
