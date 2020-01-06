from itertools import product
from sys import stdout
import json

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")

analyzer.configure_subsampler(1)  ## increase this to "skip" cycles, e.g. subsample
analyzer.configure_group(0)

# trigger conditions will depend upon each other in sequence
analyzer.add_rising_edge_trigger("puf_reset")

analyzer.run(offset=8, length=512)  ### CHANGE THIS TO MATCH DEPTH offset=32 by default

with open("test/csr.json") as csr_file:
    csr = json.load(csr_file)

csr_registers = csr["csr_registers"]

reset = csr_registers["teropuf_reset"]
cell_select = (
    csr_registers["teropuf_cell0_select"],
    csr_registers["teropuf_cell1_select"]
)
puf_val = csr_registers["teropuf_bit_value"]

for i, j in product(range(2), repeat=2):
    wb.write(reset['addr'], 1) # enable reset
    wb.write(cell_select[0]['addr'], i)
    wb.write(cell_select[1]['addr'], j)
    wb.write(reset['addr'], 0) # disable reset
    print(f'Comparator from set {i} and {j}:')
    for _ in range(10):
        print(wb.read(puf_val['addr']))

analyzer.wait_done()
analyzer.upload()
analyzer.save("test/dump.vcd")

wb.close()
