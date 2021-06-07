from itertools import product, count
import itertools
from sys import stdout
import time
import json
import ctypes

from litex.tools.litex_client import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--samples', type=int, default=-1)
parser.add_argument('--dumpfile', default='dump.py')

args = parser.parse_args()
samples_iter = range(args.samples) if args.samples >= 0 else count() 

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True, config_csv="test/analyzer.csv")

analyzer.run(length=2**20)  ### CHANGE THIS TO MATCH DEPTH offset=32 by default

with open('entropy.dat', 'ab') as f:
    for _ in samples_iter:
        wb.regs.trng_update_value.write(1)
        while not wb.regs.trng_ready.read():
            pass
        random_word = wb.regs.trng_random_word.read()
        print(hex(random_word))
        f.write(random_word.to_bytes(4, 'big'))

analyzer.wait_done()
analyzer.upload()
analyzer.save(f"test/{args.dumpfile}")

wb.close()
