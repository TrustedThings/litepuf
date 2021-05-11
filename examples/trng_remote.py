from itertools import product
from sys import stdout
import json
import ctypes

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")

analyzer.run(length=2**20)  ### CHANGE THIS TO MATCH DEPTH offset=32 by default

with open('delete_me.dat', 'ab') as f:
    for i in range(10):
        random_word16 = wb.regs.trng_random_word.read()
        print(hex(random_word16))
        f.write(random_word16.to_bytes(2, 'big'))

analyzer.wait_done()
analyzer.upload()
analyzer.save("test/dump.py")

wb.close()
