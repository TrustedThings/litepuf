#!/bin/bash
for OSC_NUM in 2 4 8 16
do
  for OSC_LEN in 3 5 7 9
  do
    python examples/trng_bench.py --num-oscillators 2 --oscillators-length 7 --load
    sleep 5
    python examples/trng_remote.py --samples 1 --dumpfile "dump_metastable_${OSC_NUM}_${OSC_LEN}.py"
    echo "dump_metastable_${OSC_NUM}_${OSC_LEN}.py"
  done
done
