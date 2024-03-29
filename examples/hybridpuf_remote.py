from itertools import product
from sys import stdout
import time
from collections import defaultdict
import json
import ctypes

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")

analyzer.configure_subsampler(1024)  ## increase this to "skip" cycles, e.g. subsample
analyzer.configure_group(0)

# trigger conditions will depend upon each other in sequence
analyzer.add_falling_edge_trigger("puf_reset")

analyzer.run(offset=8, length=512)  ### CHANGE THIS TO MATCH DEPTH offset=32 by default

samples = defaultdict(list)
for s1, s2 in product(range(5), repeat=2):
    for sample_idx in range(10): # take n samples
        wb.regs.hybridpuf_reset.write(1) # enable reset
        wb.regs.hybridpuf_cell0_select.write(s1)
        wb.regs.hybridpuf_cell1_select.write(s2)
        wb.regs.hybridpuf_reset.write(0) # disable reset
        time.sleep(0.1)
        bit_value = wb.regs.hybridpuf_bit_value.read()
        samples[f'{s1}:{s2}'].append(bit_value)
        print(f'Comparator from set {s1} and {s2}: {bit_value}')

dump = json.dumps({
    'ident': None,
    'dump': samples
})
print(dump)

analyzer.wait_done()
analyzer.upload()
analyzer.save("test/dump.vcd")

wb.close()
