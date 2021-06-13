from itertools import permutations, starmap
from functools import lru_cache
import argparse
from glob import glob
import json
from statistics import mode, mean
from operator import sub, itemgetter
from collections import defaultdict
import ctypes

from metastable.evaluation import steadiness, uniqueness, graycode

import matplotlib.pyplot as plt


def _response_post(response):
    """Return the post-processed response."""
    response = ctypes.c_bool(response).value
    return response

def response_gen(dump_iter, offset, offset_attr=None):
    for chip_dump in dump_iter:
        chip = dict()
        for c, responses in chip_dump.items():
            if offset_attr is not None:
                responses = filter(lambda r: offset_attr in r and r[offset_attr] == offset, responses)
            else:
                responses = filter(lambda r: r.keys() <= {"value"}, responses)
            responses = [_response_post(r['value']) for r in responses]
            chip[c] = responses
        yield chip

def _reference(chip):
    return {c: mode(responses) for c, responses in chip.items()}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', type=float)
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)

    response_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)
        response_dumps.append(response_data['dump'])

    #offsets = analyzer_dumps[0].keys()
    #offset_dim = 'voltage'
    offset_dim = 'offset'

    offsets = [r[offset_dim] for r in list(response_dumps[0].values())[0] if offset_dim in r]
    offsets = list(dict.fromkeys(offsets)) # remove duplicates and keep order (Python > 3.6) 

    steadiness_plot_data = []
    steadiness_err_data  = []
    uniqueness_plot_data = []

    if args.ref:
        ref_offset = args.ref
        chips = response_gen(response_dumps, ref_offset, offset_dim)
        references_per_chip = [_reference(chip) for chip in chips]
    for offset in offsets:
        chips = list(response_gen(response_dumps, offset, offset_dim))

        uniqueness_ = uniqueness(chips)
        uniqueness_plot_data.append(uniqueness_)

        steadiness_per_chip = []
        for chip_idx, chip in enumerate(chips):
            if args.ref:
                references = references_per_chip[chip_idx]
            else:
                references = _reference(chip)

            steadiness_ = list(steadiness(chip, references))
            steadiness_chip = mean(steadiness_)
            steadiness_per_chip.append(steadiness_chip)
        # plot steadiness for one chip
        steadiness_mean = mean(steadiness_per_chip)
        steadiness_plot_data.append(steadiness_mean)
        steadiness_err = steadiness_mean-min(steadiness_per_chip), max(steadiness_per_chip)-steadiness_mean
        steadiness_err_data.append(steadiness_err)

    fig, (ax_steadiness, ax_uniqueness) = plt.subplots(2)
    ax_steadiness.title.set_text('Steadiness')
    ax_uniqueness.title.set_text('Uniqueness')
    ax_steadiness.set_ylim([0, 1])
    ax_uniqueness.set_ylim([0, 1])

    yerr = (
        list(map(itemgetter(0), steadiness_err_data)),
        list(map(itemgetter(1), steadiness_err_data))
    )

    ax_steadiness.errorbar(offsets, steadiness_plot_data, yerr=yerr, fmt='ko', linestyle='-', fillstyle='none')

    ax_uniqueness.plot(
        offsets, uniqueness_plot_data, 'x-',
    )

    plt.show()
