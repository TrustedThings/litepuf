#!/usr/bin/env python3

import time
from statistics import mean

from litex import RemoteClient

wb = RemoteClient(csr_csv="test/csr.csv")
wb.open()

# # #

# Read frequency meter
fmeter_values = []
print("Reading frequency...")
for i in range(100):
    fmeter_value = wb.regs.fmeter_value.read()
    print(fmeter_value)
    fmeter_values.append(fmeter_value)
    time.sleep(1.0)
print(f'average: {mean(fmeter_values)}')
