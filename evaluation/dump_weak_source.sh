#!/bin/bash
for OSC_NUM in 2 4 6 8 10
do
  for OSC_LEN in 3 5 7 9 11     
  do
    echo "dump_weak_${OSC_NUM}_${OSC_LEN}.py"
    sleep 1
    python examples/trng_bench.py --num-oscillators $OSC_NUM --oscillators-length $OSC_LEN --load
    sleep 5
    python examples/trng_remote.py --samples 1 --dumpfile "dump_weak_${OSC_NUM}_${OSC_LEN}.py"
  done
done