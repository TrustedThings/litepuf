from itertools import permutations
import argparse
from glob import glob
import json
from statistics import mode, mean
from operator import sub, itemgetter
from collections import defaultdict
from itertools import starmap
import ctypes

from .stats import steadiness, uniqueness, graycode

import matplotlib.pyplot as plt


def chip_post_iter(dumps, offset, bit_slice=None):
    slice_bits = lambda n: int(bin(n)[2:].zfill(16)[bit_slice], 2)
    for chip in map(itemgetter(offset), dumps):
        chip_item = {}
        for challenge, responses in chip.items():
            responses_post = [ctypes.c_uint16(r).value for r in responses]
            responses_post = map(graycode, responses_post)
            if bit_slice:
                responses_post = map(slice_bits, responses_post)
            chip_item[challenge] = list(responses_post)
        yield chip_item

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)

    response_dumps = []
    analyzer_dumps = []
    voltage_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)
        response_dumps.append(response_data['dump'])
        analyzer_dumps.append(response_data['analyzer'])
        voltage_dumps.append(response_data['voltage'])

    steadiness_plot_data = defaultdict(list)
    steadiness_err_data = defaultdict(list)
    uniqueness_plot_data = defaultdict(list)

    #offsets = analyzer_dumps[0].keys()
    offsets = voltage_dumps[0].keys()

    for bit_num in range(16):
        for offset in offsets:
            #chips = list(chip_post_iter(analyzer_dumps, offset, slice(bit_num, bit_num+1)))
            chips = list(chip_post_iter(voltage_dumps, offset, slice(bit_num, bit_num+1)))
            #uniqueness_ = uniqueness(chips, response_len=1)
            uniqueness_ = 0
            uniqueness_plot_data[bit_num].append(uniqueness_)
            for chip in chips:
                references = {c: mode(responses) for c, responses in chip.items()}
                steadiness_ = list(steadiness(chip, references, response_len=1))
                steadiness_mean = mean(steadiness_)
                steadiness_plot_data[bit_num].append(steadiness_mean)
                steadiness_err = steadiness_mean-min(steadiness_), max(steadiness_)-steadiness_mean
                steadiness_err_data[bit_num].append(steadiness_err)
                # plot steadiness for one chip
                break

    fig, (ax_steadiness, ax_uniqueness) = plt.subplots(2)

    yerr = [(
        list(map(itemgetter(0), steadiness_err_data[bit_num])),
        list(map(itemgetter(1), steadiness_err_data[bit_num]))
    ) for bit_num in range(16)]
    ax_steadiness.errorbar(offsets, steadiness_plot_data[0], yerr=yerr[0], fmt='yo-') # bit 15
    ax_steadiness.errorbar(offsets, steadiness_plot_data[11], yerr=yerr[11], fmt='o-') # bit 4
    ax_steadiness.errorbar(offsets, steadiness_plot_data[10], yerr=yerr[10], fmt='o-') # bit 5
    ax_steadiness.errorbar(offsets, steadiness_plot_data[9], yerr=yerr[9], fmt='o-') # bit 6

    ax_uniqueness.plot(
        offsets, uniqueness_plot_data[0], 'x-',
        offsets, uniqueness_plot_data[11], 'x-',
        offsets, uniqueness_plot_data[10], 'x-',
        offsets, uniqueness_plot_data[9], 'x-',
    )

    plt.show()
