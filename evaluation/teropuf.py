import argparse
from pathlib import Path
from glob import glob
import json
from statistics import mode, mean
from operator import itemgetter
import ctypes
from cycler import cycler

from metastable.evaluation import steadiness, uniqueness, graycode

import matplotlib
import matplotlib.pyplot as plt


def _slice_bits(n, slicer):
    bits = bin(n)[2:].zfill(16)
    if type(slicer) is slice:
        bits = bits[slicer]
    else:
        bits = ''.join(itemgetter(*slicer)(bits))
    return int(bits, 2)

def _response_post(response, bit_slice):
    """Return the post-processed response."""
    response = ctypes.c_uint16(response).value
    response = graycode(response)
    if bit_slice:
        response = _slice_bits(response, bit_slice)
    return response

def response_gen(dump_iter, offset_attr, offset=None, bit_slice=None):        
    for chip_dump in dump_iter:
        chip = dict()
        for c, responses in chip_dump.items():
            if offset_attr is not None:
                responses = filter(lambda r: offset_attr in r and r[offset_attr] == offset, responses)
            else:
                # remove all values with additional offset attribute(s)
                responses = filter(lambda r: r.keys() <= {"value"}, responses)
            responses = [_response_post(r['value'], bit_slice) for r in responses]
            chip[c] = responses
        yield chip

def _reference(chip):
    return {c: mode(responses) for c, responses in chip.items()}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', type=float, help='reference offset for steadiness (sliding by default)')
    parser.add_argument('--offset-key', default=None)
    parser.add_argument('--export-path', default=None, help='export path of plot figure')
    parser.add_argument('--yerr', action='store_true', default=False)
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    matplotlib.rcParams['axes.prop_cycle'] = cycler(color='rbgcmyk') # default color='bgrcmyk
    if args.export_path:
        path = Path(args.export_path)
        if path.suffix != '.pgf':
            raise ValueError('only pgf export is supported')
        matplotlib.use("pgf")
        matplotlib.rcParams.update({
            "pgf.texsystem": "pdflatex",
            'font.family': 'serif',
            'text.usetex': True,
            'pgf.rcfonts': False,
        })

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)

    response_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)
        response_dumps.append(response_data['dump'])

    offset_attr = args.offset_key
    if offset_attr:
        offsets = [r[offset_attr] for r in list(response_dumps[0].values())[0] if offset_attr in r]
        offsets = list(dict.fromkeys(offsets)) # remove duplicates and keep order (Python > 3.6) 
    else:
        offsets = [None,]

    # TODO: configure slices in args
    #slices = [slice(bit_num, bit_num+1) for bit_num in range(16)]
    #slices = [[0], [9, 10, 11]]
    slices = [[0], [15], [14], [13], [12], [11]]

    steadiness_plot_data = [list() for _ in range(len(slices))]
    steadiness_err_data  = [list() for _ in range(len(slices))]
    uniqueness_plot_data = [list() for _ in range(len(slices))]

    for slice_idx, bit_slice in enumerate(slices):
        if args.ref:
            ref_offset = args.ref
            chips = response_gen(response_dumps, offset_attr, ref_offset, bit_slice)
            references_per_chip = [_reference(chip) for chip in chips]
        for offset in offsets:
            chips = list(response_gen(response_dumps, offset_attr, offset, bit_slice))

            # get length from the slice
            if type(bit_slice) is slice:
                slice_len = len(range(*bit_slice.indices(16)))
            else:
                slice_len = len(bit_slice)
            print(f'Slice {slice_idx} len: {slice_len}')
            uniqueness_ = uniqueness(chips, response_len=slice_len)
            uniqueness_plot_data[slice_idx].append(uniqueness_)

            steadiness_per_chip = []
            for chip_idx, chip in enumerate(chips):
                if args.ref:
                    references = references_per_chip[chip_idx]
                else:
                    references = _reference(chip)

                steadiness_ = list(steadiness(chip, references, response_len=slice_len))
                steadiness_chip = mean(steadiness_)
                steadiness_per_chip.append(steadiness_chip)
            # plot steadiness for one chip
            steadiness_mean = mean(steadiness_per_chip)
            steadiness_plot_data[slice_idx].append(steadiness_mean)
            steadiness_err = steadiness_mean-min(steadiness_per_chip), max(steadiness_per_chip)-steadiness_mean
            steadiness_err_data[slice_idx].append(steadiness_err)
            print('Uniqueness:', uniqueness_)
            print('Steadiness:', steadiness_mean, steadiness_per_chip)

    fig, (ax_uniqueness, ax_steadiness) = plt.subplots(2)
    fig.tight_layout(pad=3.0)
    fig.set_figheight(6)
    fig.set_figwidth(7)

    ax_steadiness.set(xlabel='Acquisition time in clock cycles (50 Mhz)', ylabel='Steadiness',
            title=None)
    ax_uniqueness.set(xlabel='Acquisition time in clock cycles (50 Mhz)', ylabel='Uniqueness')
    ax_steadiness.set_ylim([0.5, 1])
    ax_steadiness.margins(x=0.02)
    ax_uniqueness.set_ylim([0, 0.6])
    ax_uniqueness.margins(x=0.02)

    if args.yerr:
        yerr = [(
            list(map(itemgetter(0), steadiness_err_data[slice_idx])),
            list(map(itemgetter(1), steadiness_err_data[slice_idx]))
        ) for slice_idx in range(len(slices))]
    else:
        yerr = [None] * len(slices)

    ax_steadiness.errorbar(offsets, steadiness_plot_data[0], yerr=yerr[0], fmt='o-', markersize=3, markeredgewidth=1, label='bit 15')
    ax_steadiness.errorbar(offsets, steadiness_plot_data[1], yerr=yerr[1], fmt='o-', markersize=3, markeredgewidth=1, label='bit 0')
    ax_steadiness.errorbar(offsets, steadiness_plot_data[2], yerr=yerr[2], fmt='o-', markersize=3, markeredgewidth=1, label='bit 1')
    ax_steadiness.errorbar(offsets, steadiness_plot_data[3], yerr=yerr[3], fmt='o-', markersize=3, markeredgewidth=1, label='bit 2')
    ax_steadiness.errorbar(offsets, steadiness_plot_data[4], yerr=yerr[4], fmt='o-', markersize=3, markeredgewidth=1, label='bit 3')
    ax_steadiness.errorbar(offsets, steadiness_plot_data[5], yerr=yerr[5], fmt='o-', markersize=3, markeredgewidth=1, label='bit 4')

    ax_uniqueness.plot(offsets, uniqueness_plot_data[0], 'o-', markersize=3, markeredgewidth=1)
    ax_uniqueness.plot(offsets, uniqueness_plot_data[1], 'o-', markersize=3, markeredgewidth=1)
    ax_uniqueness.plot(offsets, uniqueness_plot_data[2], 'o-', markersize=3, markeredgewidth=1)
    ax_uniqueness.plot(offsets, uniqueness_plot_data[3], 'o-', markersize=3, markeredgewidth=1)
    ax_uniqueness.plot(offsets, uniqueness_plot_data[4], 'o-', markersize=3, markeredgewidth=1)
    ax_uniqueness.plot(offsets, uniqueness_plot_data[5], 'o-', markersize=3, markeredgewidth=1)

    fig.legend(loc="lower right", bbox_to_anchor=(1,0), bbox_transform=ax_uniqueness.transAxes, ncol=2)

    if args.export_path:
        # plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
        plt.savefig(args.export_path, bbox_inches='tight', pad_inches=0)
    else:
        plt.show()
