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

    
_get_bit = lambda n, i: n >> i & 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)

    response_dumps = []
    analyzer_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)
        response_dumps.append(response_data['dump'])
        analyzer_dumps.append(response_data['analyzer'])

    chip_offset_cr_list = []

    for chip in analyzer_dumps:
        steadiness_plot_data = defaultdict(list)
        offset_cr_dict = dict()
        chip_offset_cr_list.append(offset_cr_dict)

        for offset, cr in chip.items():
            # challenge-responses for offset
            offset_cr_dict[offset] = cr_dict = dict()

            for challenge, responses in cr.items():
                responses_gray = [ctypes.c_uint16(r).value for r in responses]
                responses_gray = list(map(graycode, responses_gray))
                cr_dict[challenge] = responses_gray

            for bit_num in range(16):
                cr_bit_dict = {c: list(map(lambda r: _get_bit(r, bit_num), responses)) for c, responses in cr_dict.items()}
                references = {c: mode(responses) for c, responses in cr_bit_dict.items()}
                steadiness_ = mean(steadiness(cr_bit_dict, references, response_len=1))

                steadiness_plot_data[bit_num].append(steadiness_)

        plt.plot(
            chip.keys(), steadiness_plot_data[0], 'r--',
            chip.keys(), steadiness_plot_data[1], 'g--',
            chip.keys(), steadiness_plot_data[2], 'b--',
            chip.keys(), steadiness_plot_data[13], 'r^',
            chip.keys(), steadiness_plot_data[14], 'g^',
            chip.keys(), steadiness_plot_data[15], 'b^',
        )

    for offset in analyzer_dumps[0]:
        cr_dict = list(map(itemgetter(offset), chip_offset_cr_list))
        for bit_num in range(16):
            uniqueness_ = uniqueness(cr_dict, response_len=1)

    plt.show()
