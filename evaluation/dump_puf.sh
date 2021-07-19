#!/bin/bash
CELLS=96
SAMPLES=10
FPGA_ID=0
for PUF_TYPE in RO TERO HYBRID
do
  python examples/puf_bench.py --type $PUF_TYPE --load
  sleep 5
  timestamp=$(date +%s)
  python examples/puf_remote.py --cells ${CELLS} --type $PUF_TYPE --samples ${SAMPLES} --identity "${PUF_TYPE}-${FPGA_ID}_${CELLS}_${SAMPLES}-${timestamp}"
  python examples/puf_remote.py --analyzer --cells ${CELLS} --type $PUF_TYPE --samples ${SAMPLES} --identity "${PUF_TYPE}-${FPGA_ID}_${CELLS}_${SAMPLES}_analyer-${timestamp}"
done
