#!/usr/bin/env python3

import argparse
import os
from itertools import cycle, islice, chain, count

from migen import *

from litex.soc.cores.uart import UARTWishboneBridge
from litex.soc.integration.builder import Builder

from litex.build.generic_platform import Subsignal, IOStandard, Pins

from litex_boards.platforms import ecp5_evn
from litex_boards.targets.ecp5_evn import BaseSoC

from litescope import LiteScopeAnalyzer

from litepuf import RingOscillator
from litepuf.oscillator import MetastableOscillator
from litepuf.random import RandomLFSR

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

    def __init__(self, num_osc=4, osc_len=7):
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

        oscillators = [RingOscillator(placement) for placement in ro_placer(num_osc, osc_len)]
        self.submodules.trng = trng = RandomLFSR(oscillators)

        # Litescope Analyzer
        analyzer_groups = {}

        analyzer_groups[0] = [
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


def main():
    parser = argparse.ArgumentParser(description="TRNG testbench on ECP5 Evaluation Board")
    parser.add_argument("--load",         action="store_true", help="Load bitstream")
    parser.add_argument('--num-oscillators', type=int, default=4)
    parser.add_argument('--oscillators-length', type=int, default=7)
    args = parser.parse_args()

    soc = LiteScopeSoC(
        num_osc=args.num_oscillators,
        osc_len=args.oscillators_length)
    builder = Builder(soc, csr_csv="test/csr.csv", csr_json="test/csr.json")
    vns = builder.build(nowidelut=True, ignoreloops=True)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".svf"))

if __name__ == "__main__":
    main()
