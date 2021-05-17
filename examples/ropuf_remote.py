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

for i, j in product(range(10), repeat=2):
    wb.regs.ropuf_reset.write(1) # enable reset
    wb.regs.ropuf_cell0_select.write(i)
    wb.regs.ropuf_cell1_select.write(j)
    wb.regs.ropuf_reset.write(0) # disable reset
    time.sleep(0.2)
    bit_value = wb.regs.ropuf_bit_value.read()
    print(f'Comparator from set {i} and {j}: {bit_value}')

analyzer.wait_done()
analyzer.upload()
analyzer.save("test/dump.vcd")

wb.close()
