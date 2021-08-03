from functools import reduce
from itertools import zip_longest
from importlib import import_module
from tempfile import NamedTemporaryFile
import subprocess

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

bits2bytes = lambda bits: [reduce(lambda byte, bit: byte << 1 | bit, eight_bits)
         for eight_bits in grouper(bits, 8, fillvalue=0)]

oscillator_counts = [2, 4, 6, 8, 10]
inverter_counts = [3, 5, 7, 9, 11]

for osc_idx, osc_count in enumerate(oscillator_counts):
    for inv_idx, inv_count in enumerate(inverter_counts):
        dump = import_module(f'dump_weak_{osc_count}_{inv_count}')

        metastable = dump.dump["soc_trng_metastable"]

        with NamedTemporaryFile() as fp:
            fp.write(bytes(bits2bytes(metastable[::2])))
            fp.seek(0)

            process = subprocess.run(['convert', '-depth', '1', '-size', '1000x320', 'mono:-', f'{osc_count}_{inv_count}.png'], 
                                stdin=fp, capture_output=True)
