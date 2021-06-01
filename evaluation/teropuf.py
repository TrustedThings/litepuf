from itertools import permutations
from functools import lru_cache
import argparse
from glob import glob
import json
from statistics import mode, mean
from operator import sub, itemgetter
from collections import defaultdict
from itertools import starmap
import ctypes

from metastable.evaluation import steadiness, uniqueness, graycode

import matplotlib.pyplot as plt


def postprocess_response(response, bit_slice=None):
    # mask of response bits
    slice_bits = lambda n: int(bin(n)[2:].zfill(16)[bit_slice], 2)
    response = ctypes.c_uint16(response).value
    response = graycode(response)
    if bit_slice:
        response = slice_bits(response)
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)

    response_dumps = []
    #analyzer_dumps = []
    #voltage_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)
        response_dumps.append(response_data['dump'])
        #analyzer_dumps.append(response_data['analyzer'])
        #voltage_dumps.append(response_data['voltage'])

    steadiness_plot_data = defaultdict(list)
    steadiness_err_data = defaultdict(list)
    uniqueness_plot_data = defaultdict(list)

    #offsets = analyzer_dumps[0].keys()
    offset_dim = 'voltage'

    offsets = [r[offset_dim] for r in list(response_dumps[0].values())[0] if offset_dim in r]
    offsets = list(dict.fromkeys(offsets)) # remove duplicates and keep order (Python > 3.6) 

    slices = [None]
    #slices = [slice(bit_num, bit_num+1) for bit_num in range(16)]

    steadiness_plot_data = [list() for _ in range(len(slices))]
    steadiness_err_data = [list() for _ in range(len(slices))]
    uniqueness_plot_data = [list() for _ in range(len(slices))]

    for slice_idx, bit_slice in enumerate(slices):
        for offset in offsets:
            #chips = list(chip_post_iter(analyzer_dumps, offset, slice(bit_num, bit_num+1)))
            chips = []
            for chip_dump in response_dumps:
                chip = dict()
                for c, responses in chip_dump.items():
                    responses = list(filter(lambda r: offset_dim in r and r[offset_dim] == offset, responses))
                    #responses = [postprocess_response(r['value'], slice(bit_num, bit_num+1)) for r in responses]
                    responses = [postprocess_response(r['value'], bit_slice) for r in responses]
                    chip[c] = responses
                chips.append(chip)

            uniqueness_ = uniqueness(chips, response_len=1)
            uniqueness_plot_data[slice_idx].append(uniqueness_)

            for chip in chips:
                references = {c: mode(responses) for c, responses in chip.items()}
                steadiness_ = list(steadiness(chip, references, response_len=1))
                steadiness_mean = mean(steadiness_)
                # plot steadiness for one chip
                steadiness_plot_data[slice_idx].append(steadiness_mean)
                steadiness_err = steadiness_mean-min(steadiness_), max(steadiness_)-steadiness_mean
                steadiness_err_data[slice_idx].append(steadiness_err)
                break

    fig, (ax_steadiness, ax_uniqueness) = plt.subplots(2)

    yerr = [(
        list(map(itemgetter(0), steadiness_err_data[slice_idx])),
        list(map(itemgetter(1), steadiness_err_data[slice_idx]))
    ) for slice_idx in range(len(slices))]

    ax_steadiness.errorbar(offsets, steadiness_plot_data[0], fmt='ro', linestyle='-') # bit 15
    #ax_steadiness.errorbar(offsets, steadiness_plot_data[11], yerr=yerr[11], fmt='o-') # bit 4
    #ax_steadiness.errorbar(offsets, steadiness_plot_data[10], yerr=yerr[10], fmt='o-') # bit 5
    #ax_steadiness.errorbar(offsets, steadiness_plot_data[9], yerr=yerr[9], fmt='o-') # bit 6
    #ax_steadiness.errorbar(offsets, steadiness_plot_data[15], fmt='rx-') # bit 0

    ax_uniqueness.plot(
        offsets, uniqueness_plot_data[0], 'x-',
        #offsets, uniqueness_plot_data[11], 'x-',
        #offsets, uniqueness_plot_data[10], 'x-',
        #offsets, uniqueness_plot_data[9], 'x-',
    )

    plt.show()
