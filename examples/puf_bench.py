#!/usr/bin/env python3

import argparse
import os
from enum import Enum, auto

from itertools import cycle, islice, chain, count
from time import monotonic
from more_itertools import grouper

from migen import *
from migen.genlib.io import CRG

from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.integration.builder import Builder

from litex.build.generic_platform import Subsignal, IOStandard, Pins

from litex_boards.platforms import ecp5_evn
from litex_boards.targets.ecp5_evn import BaseSoC

from litescope import LiteScopeIO, LiteScopeAnalyzer

from metastable import RingOscillator, TEROCell
from metastable.oscillator import MetastableOscillator
from metastable.cores import RingOscillatorPUF, TransientEffectRingOscillatorPUF as TEROPUF, PowerOptimizedHybridOscillatorArbiterPUF as HybridOscillatorArbiterPUF
from metastable.random import RandomLFSR

from metastable import PUFType


def slicer():
    slice_iter = cycle("ABCD")
    for i in count(0):
        for _ in range(4):
            yield (i, next(slice_iter))

def ro_placer(num_chains, chain_length, x_start=4, y_start=11):
    for chain in range(num_chains):
        placement = [f"X{x_start+column}/Y{y_start+chain}/SLICE{slice_id}" for column, slice_id in islice(slicer(), chain_length)]
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

    def __init__(self, puf_type):
        sys_clk_freq = int(50e6) # check

        BaseSoC.__init__(self, sys_clk_freq, x5_clk_freq=50e6, toolchain="trellis", # check
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
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

        oscillators1 = []
        oscillators2 = []

        if puf_type is PUFType.RO:
            p_iter = chain(*[
                ro_placer(8, 7, x_start=4, y_start=11),
                ro_placer(8, 7, x_start=7, y_start=11),
                ro_placer(8, 7, x_start=10, y_start=11),
                ro_placer(8, 7, x_start=13, y_start=11),
            ])
            for p1, p2 in grouper(p_iter, 2):
                oscillators1.append(RingOscillator(p1))
                oscillators2.append(RingOscillator(p2))
            self.submodules.puf = puf = RingOscillatorPUF((oscillators1, oscillators2))
            self.comb += puf_reset.eq(puf.reset)
        elif puf_type is PUFType.TERO:
            p_iter = tero_placer(8, 7)
            for p1, p2 in grouper(p_iter, 2):
                oscillators1.append(TEROCell(p1))
                oscillators2.append(TEROCell(p2))
            self.submodules.puf = puf = TEROPUF((oscillators1, oscillators2))
            self.comb += puf_reset.eq(puf.reset)
        elif puf_type is PUFType.HYBRID:
            p_iter = ro_placer(10, 8)
            for p1, p2 in grouper(p_iter, 2):
                oscillators1.append(RingOscillator(p1))
                oscillators2.append(RingOscillator(p2))
            self.submodules.puf = puf = HybridOscillatorArbiterPUF((oscillators1, oscillators2))

        self.comb += puf_reset.eq(puf.reset)

        # safety check for the scope sampling rate
        monotonic = Signal(16)
        self.sync += monotonic.eq(monotonic + 1)

        # puf group
        analyzer_groups[0] = [
            puf.bit_value,
            puf_reset,
            # puf.ro_set0.counter,
            # puf.ro_set1.counter,
            puf.ro_set0.ring_out,
            puf.ro_set1.ring_out,
            puf.ro_set0.select,
            puf.ro_set1.select,
            monotonic
            # puf.pulse_comp.select,
            # puf.pulse_comp.ready
        ]
        if hasattr(puf, "_cell0_select"):
           analyzer_groups[0].append(puf._cell0_select.storage) 
        if hasattr(puf, "_cell1_select"):
           analyzer_groups[0].append(puf._cell1_select.storage)
        if puf.puf_type is PUFType.RO or puf.puf_type is PUFType.TERO:
            analyzer_groups[0].append(puf.ro_set0.counter)
            analyzer_groups[0].append(puf.ro_set1.counter)
        elif puf.puf_type is PUFType.HYBRID:
            analyzer_groups[0].append(puf.ff_o)

        # analyzer
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_groups,
            depth=512,
            csr_csv="test/analyzer.csv")


def main():
    parser = argparse.ArgumentParser(description="PUF testbench on ECP5 Evaluation Board")
    parser.add_argument("--load",         action="store_true", help="Load bitstream")
    parser.add_argument('--type', type=lambda t: PUFType[t], choices=list(PUFType), required=True)
    args = parser.parse_args()

    soc = LiteScopeSoC(puf_type=args.type)
    builder = Builder(soc, csr_csv="test/csr.csv", csr_json="test/csr.json")
    vns = builder.build(nowidelut=True, ignoreloops=True)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".svf"))

if __name__ == "__main__":
    main()
