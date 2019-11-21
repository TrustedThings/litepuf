#!/usr/bin/env python3

from itertools import cycle, islice, chain, count
from os import path

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
        yield [f"X{4+column}/Y{11+chain}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)]

def tero_placer(num_cells, chain_length):
    for cell in range(num_cells):
        yield (
            [f"X{2+column}/Y{2+cell}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)],
            [f"X{4+column}/Y{2+cell}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)],
        )


class LiteScopeSoC(BaseSoC):
    csr_map = {
        "io":       16,
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

        self.platform.add_source_dir(path.join(path.dirname(__file__), 'verilog/lattice_ecp5'))
        self.platform.add_source(path.join(path.dirname(__file__), 'verilog/lfsr.v'))
        self.platform.add_source(path.join(path.dirname(__file__), 'verilog/random.v'))

        metastable = Signal(name_override="metastable")
        metastable.attr.add("keep")
        rand_out = Signal(8, name_override="lfsr_weak")
        
        chain_out = Signal(name_override="chain_out")#, attr=set(["keep", ("noglobal", "1")]))
        chain_out.attr.add("keep")
        chain_out.attr.add(("noglobal", None))
        
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

        osci = MetastableOscillator(*[RingOscillator([None]*3) for _ in range(4)])
        self.submodules.trng = trng = RandomLFSR(osci)

        analyzer_groups[0] = [
            rand_out,
            metastable
        ]

        analyzer_groups[1] = [
            trng.word_ready,
            trng.reset,
            trng.shiftreg
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

csr_csv = cpu_interface.get_csr_csv(soc.csr_regions, soc.constants, soc.mem_regions)
csr_json = cpu_interface.get_csr_json(soc.csr_regions, soc.constants, soc.mem_regions)
write_to_file("test/csr.csv", csr_csv)
write_to_file("test/csr.json", csr_json)
soc.do_exit(vns)
