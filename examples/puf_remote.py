from itertools import product, count
from sys import stdout
import time
from collections import defaultdict
import json
from more_itertools import numeric_range
from decimal import Decimal
from ctypes import *
from enum import Enum, auto

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver
from litescope.software.dump import DumpData, Dump

from metastable import PUFType

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--identity", default=None)
parser.add_argument('--analyzer', action='store_true')
parser.add_argument('--voltage', action='store_true')
parser.add_argument('--samples', type=int, default=100)
parser.add_argument('--type', type=lambda t: PUFType[t], choices=list(PUFType))

args = parser.parse_args()
wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

samples = defaultdict(list)
samples_iter = range(args.samples)

if args.analyzer:
    analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")
    subsampling = 10
    analyzer.configure_subsampler(subsampling)  ## increase this to "skip" cycles, e.g. subsample
    analyzer.configure_group(0)

if args.voltage:
    from dwfconstants import *

    dwf = cdll.LoadLibrary("libdwf.so")
    hdwf = c_int()

    print("Opening first device")
    dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

    if hdwf.value == hdwfNone.value:
        print("failed to open device")
        quit()

    # set up analog IO channel nodes
    # enable positive supply
    dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(0), c_double(True))
    # set voltage to 1.15 V
    dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(1), c_double(1.15))
    # master enable
    dwf.FDwfAnalogIOEnableSet(hdwf, c_int(True))

    if True:
        time.sleep(120)

    def voltage_range(start, stop, step):
        # max recommended operating conditions for ECP5-5G is 1.26V
        # absolute maximum rating is 1.32V for ECP5 and ECP5-5G
        assert(start <= stop <= 1.32)
        return numeric_range(start, stop, step)

    voltage_iter = voltage_range(Decimal('1.1'), Decimal('1.31'), Decimal('0.02'))
    samples_iter = product(samples_iter, voltage_iter)

samples_iter = list(samples_iter)
for s1, s2 in product(range(5), repeat=2):
    for sample_idx in samples_iter: # take n samples
        sample = {}
        if args.analyzer:
            analyzer.clear()
            analyzer.add_falling_edge_trigger("puf_reset")
            analyzer.run(offset=0, length=51)
        if args.voltage:
            voltage = float(sample_idx[1])
            if dwf.FDwfAnalogIOStatus(hdwf) == 0:
                break
            sample['voltage'] = voltage
            print(f'set voltage to {voltage}')
            dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(1), c_double(voltage))
            time.sleep(0.3)

        wb.regs.puf_reset.write(1) # enable reset
        wb.regs.puf_cell0_select.write(s1)
        wb.regs.puf_cell1_select.write(s2)
        wb.regs.puf_reset.write(0) # disable reset
        time.sleep(0.1)
        bit_value = wb.regs.puf_bit_value.read()
        sample['value'] = bit_value
        print(f'Comparator from set {s1} and {s2}: {c_int16(bit_value).value}')

        samples[f'{s1}:{s2}'].append(sample)

        if args.analyzer:
            analyzer.wait_done()
            analyzer.upload()
            analyzer_dump = Dump()
            analyzer_dump.add_from_layout(analyzer.layouts[analyzer.group], analyzer.data)

            if args.type is PUFType.RO or args.type is PUFType.TERO:
                cv1 = next(v.values for v in  analyzer_dump.variables if v.name == 'puf_roset0_counter')
                cv2 = next(v.values for v in  analyzer_dump.variables if v.name == 'puf_roset1_counter')
                # each clock cycles has two values (rising, falling), skip every other value
                signal_values = list(zip(cv1, cv2))[::2]
            elif args.type is PUFType.HYBRID:
                signal_values = list(next(v.values for v in  analyzer_dump.variables if v.name == 'puf_ff_o'))
            for offset, signal_value in zip(count(0, subsampling), signal_values):
                if args.type is PUFType.RO or args.type is PUFType.TERO:
                    counter1, counter2 = signal_value
                    puf_response = counter1 - counter2
                elif args.type is PUFType.HYBRID:
                    puf_response = signal_value
                # index responses by offset (in clock cycles)
                sample = {
                    'offset': offset,
                    'value': puf_response
                }
                samples[f'{s1}:{s2}'].append(sample)

if args.analyzer:
    analyzer.save("test/dump.vcd")
if args.voltage:
    dwf.FDwfDeviceClose(hdwf)

wb.close()

dump = {
    'ident': args.identity,
    'dump': samples
}

with open(f'{args.identity or "puf"}_dump.json', 'w') as dumpfile:
    json.dump(dump, dumpfile)
