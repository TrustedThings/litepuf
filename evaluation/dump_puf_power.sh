#!/bin/bash
CELLS=96
SAMPLES=10
FPGA_ID=0
for PUF_TYPE in RO TERO HYBRID
do
  #dwfcmd connect analogio channel=1 enable=1 voltage=1.2 masterenable=1
  python evaluation/dwf_power.py
  python examples/puf_bench.py --type $PUF_TYPE --load
  sleep 5
  timestamp=$(date +%s)
  python examples/puf_remote.py --voltage --cells ${CELLS} --type $PUF_TYPE --samples ${SAMPLES} --identity "${PUF_TYPE}-${FPGA_ID}_${CELLS}_${SAMPLES}_power-${timestamp}"
done
