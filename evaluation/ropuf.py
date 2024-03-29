import argparse
from pathlib import Path
from glob import glob
import json
from statistics import mode, mean
from operator import itemgetter
import ctypes

from litepuf.evaluation import steadiness, uniqueness, randomness, graycode

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def _response_post(response):
    """Return the post-processed response."""
    # response = ctypes.c_bool(response).value
    # workaround, the ROPUF sampler return counter values instead of boolean
    response = ctypes.c_int16(response).value > 0
    return response

def response_gen(dump_iter, offset_attr, offset=None):        
    for chip_dump in dump_iter:
        chip = dict()
        for c, responses in chip_dump.items():
            if offset_attr is not None:
                responses = filter(lambda r: offset_attr in r and r[offset_attr] == offset, responses)
            else:
                # remove all values with additional offset attribute(s)
                responses = filter(lambda r: r.keys() <= {"value"}, responses)
            responses = [_response_post(r['value']) for r in responses]
            chip[c] = responses
        yield chip

def _reference(chip):
    return {c: mode(responses) for c, responses in chip.items()}

def parse_dumps(response_dumps, offset_attr, offset=None):
    chips = list(response_gen(response_dumps, offset_attr, offset))

    uniqueness_ = uniqueness(chips)

    steadiness_per_chip = []
    for chip_idx, chip in enumerate(chips):
        if args.ref:
            references = references_per_chip[chip_idx]
        else:
            references = _reference(chip)

        steadiness_ = list(steadiness(chip, references))
        steadiness_chip = mean(steadiness_)
        steadiness_per_chip.append(steadiness_chip)

    randomness_ = randomness(chips)
    print('Randomness:', randomness_)

    return (
        uniqueness_,
        steadiness_per_chip,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', type=float, help='reference offset for steadiness (sliding by default)')
    parser.add_argument('--offset-key', default=None)
    parser.add_argument('--export-path', default=None, help='export path of plot figure')
    parser.add_argument('--yerr', action='store_true', default=False)
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

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
    print(dump_files)

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

    steadiness_plot_data = []
    steadiness_err_data  = []
    uniqueness_plot_data = []

    if args.ref:
        ref_offset = args.ref
        chips = response_gen(response_dumps, offset_attr, ref_offset)
        references_per_chip = [_reference(chip) for chip in chips]
    for offset in offsets:
        uniqueness_, steadiness_per_chip = parse_dumps(response_dumps, offset_attr, offset)
        uniqueness_plot_data.append(uniqueness_)
        # plot steadiness for one chip
        steadiness_mean = mean(steadiness_per_chip)
        steadiness_plot_data.append(steadiness_mean)
        steadiness_err = steadiness_mean-min(steadiness_per_chip), max(steadiness_per_chip)-steadiness_mean
        steadiness_err_data.append(steadiness_err)
        print('Uniqueness:', uniqueness_)
        print('Steadiness:', steadiness_mean, steadiness_per_chip)

    fig, (ax_uniqueness, ax_steadiness) = plt.subplots(2)
    if args.offset_key == 'voltage':
        fig, ax_steadiness = plt.subplots()
        fig.set_figheight(3)
    else:
        fig.set_figheight(5)
    fig.set_figwidth(7)
    fig.tight_layout(pad=3.0)

    ax_steadiness.grid(linestyle='dotted')
    ax_uniqueness.grid(linestyle='dotted')

    xlabels = {
        'offset': 'Acquisition time in clock cycles (50 Mhz)',
        'voltage': 'Voltage (V)'
    }
    xlabel = xlabels.get(args.offset_key)
    ax_steadiness.set(xlabel=xlabel, ylabel='Steadiness',
            title=None)
    ax_uniqueness.set(xlabel=xlabel, ylabel='Uniqueness')
    ax_steadiness.set_ylim([0.5, 1])
    ax_steadiness.margins(x=0.02)
    if args.offset_key == 'voltage':
        ax_steadiness.xaxis.set_major_locator(ticker.MultipleLocator(0.02))
        ax_steadiness.yaxis.set_major_locator(ticker.MultipleLocator(0.1))
    ax_uniqueness.set_ylim([0, 0.6])
    ax_uniqueness.margins(x=0.02)
    ax_uniqueness.yaxis.set_major_locator(ticker.MultipleLocator(0.1))

    if args.yerr:
        yerr = (
            list(map(itemgetter(0), steadiness_err_data)),
            list(map(itemgetter(1), steadiness_err_data))
        )
    else:
        yerr = None

    ax_steadiness.errorbar(
        offsets, steadiness_plot_data, yerr=yerr, markersize=3, markeredgewidth=1, color='b', capsize=3, capthick=1
    )

    ax_uniqueness.plot(
        offsets, uniqueness_plot_data, markersize=3, markeredgewidth=1, color='b'
    )

    if args.export_path:
        # plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
        fig.savefig(args.export_path, bbox_inches='tight', pad_inches=0)
    else:
        plt.show()
