from itertools import product, count
from sys import stdout
import time
from collections import defaultdict
import json
import ctypes
from operator import sub

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver
from litescope.software.dump import DumpData, Dump

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--identity", default=None)
args = parser.parse_args()

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")
subsampling = 10
analyzer.configure_subsampler(subsampling)  ## increase this to "skip" cycles, e.g. subsample
analyzer.configure_group(0)

samples = defaultdict(list)
analyzer_samples = defaultdict(lambda: defaultdict(list))
for s1, s2 in product(range(4), repeat=2):
    for sample_idx in range(100): # take n samples
        analyzer.clear()
        analyzer.add_falling_edge_trigger("puf_reset")
        analyzer.run(offset=0, length=51)

        wb.regs.teropuf_reset.write(1) # enable reset
        wb.regs.teropuf_cell0_select.write(s1)
        wb.regs.teropuf_cell1_select.write(s2)
        wb.regs.teropuf_reset.write(0) # disable reset
        time.sleep(0.1)
        bit_value = wb.regs.teropuf_bit_value.read()
        two_complement = lambda x: x - 0x100000000 if x & 0x80000000 else x

        samples[f'{s1}:{s2}'].append(bit_value)
        print(f'Comparator from set {s1} and {s2}: {two_complement(bit_value)}')

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
analyzer.save("test/dump.vcd")

wb.close()

dump = {
    'ident': args.identity,
    'dump': samples,
    'analyzer': analyzer_samples
}

with open(f'{args.identity or "teropuf"}_dump.json', 'w') as dumpfile:
    json.dump(dump, dumpfile)
