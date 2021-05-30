from itertools import product, count
from sys import stdout
import time
from collections import defaultdict
import json
import ctypes
from operator import sub
from ctypes import *

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver
from litescope.software.dump import DumpData, Dump

def voltage_range(start, stop, step):
    start = float(start)
    # max recommended operating conditions for ECP5-5G is 1.26V
    # absolute maximum rating is 1.32V for ECP5 and ECP5-5G
    assert(start <= stop <= 1.32)

    count = 0
    while True:
        step_ = round(float(start + count * step), 3)
        if step > 0 and step_ >= stop:
            break
        elif step < 0 and step_ <= stop:
            break
        yield step_
        count += 1

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--identity", default=None)
parser.add_argument('--analyzer', action='store_true')
parser.add_argument('--voltage', action='store_true')
parser.add_argument('--samples', type=int, default=100)

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

    analyzer_samples = defaultdict(lambda: defaultdict(list))
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

    voltage_iter = voltage_range(1.1, 1.3, 0.02)
    samples_iter = product(samples_iter, voltage_iter)
    voltage_samples = defaultdict(lambda: defaultdict(list))

samples_iter = list(samples_iter)
for s1, s2 in product(range(4), repeat=2):
    for sample_idx in samples_iter: # take n samples
        if args.analyzer:
            analyzer.clear()
            analyzer.add_falling_edge_trigger("puf_reset")
            analyzer.run(offset=0, length=51)
        if args.voltage:
            voltage = sample_idx[1]
            if dwf.FDwfAnalogIOStatus(hdwf) == 0:
                break
            print(f'set voltage to {voltage}')
            dwf.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(1), c_double(voltage))
            time.sleep(0.3)

        wb.regs.teropuf_reset.write(1) # enable reset
        wb.regs.teropuf_cell0_select.write(s1)
        wb.regs.teropuf_cell1_select.write(s2)
        wb.regs.teropuf_reset.write(0) # disable reset
        time.sleep(0.1)
        bit_value = wb.regs.teropuf_bit_value.read()
        two_complement = lambda x: x - 0x100000000 if x & 0x80000000 else x

        samples[f'{s1}:{s2}'].append(bit_value)
        print(f'Comparator from set {s1} and {s2}: {two_complement(bit_value)}')

        if args.analyzer:
            analyzer.wait_done()
            analyzer.upload()
            analyzer_dump = Dump()
            analyzer_dump.add_from_layout(analyzer.layouts[analyzer.group], analyzer.data)
            # dumps are not indexed
            cv1 = next(v.values for v in  analyzer_dump.variables if v.name == 'teropuf_roset0_counter')
            cv2 = next(v.values for v in  analyzer_dump.variables if v.name == 'teropuf_roset1_counter')
            # each clock cycles has two values (rising, falling), skip every other value
            counter_values = list(zip(cv1, cv2))[::2]
            for offset, (counter1, counter2) in zip(count(0, subsampling), counter_values):
                puf_response = counter1 - counter2
                # index responses by offset (in clock cycles)
                analyzer_samples[offset][f'{s1}:{s2}'].append(puf_response)
        if args.voltage:
            voltage_samples[voltage][f'{s1}:{s2}'].append(bit_value)

if args.analyzer:
    analyzer.save("test/dump.vcd")
if args.voltage:
    dwf.FDwfDeviceClose(hdwf)

wb.close()

dump = {
    'ident': args.identity,
    'dump': samples,
    'analyzer': analyzer_samples if args.analyzer else [],
    'voltage': voltage_samples if args.voltage else [],
}

with open(f'{args.identity or "teropuf"}_dump.json', 'w') as dumpfile:
    json.dump(dump, dumpfile)
