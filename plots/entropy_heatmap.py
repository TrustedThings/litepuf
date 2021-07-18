from importlib import import_module
from tempfile import NamedTemporaryFile
from itertools import product
import re
import subprocess
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

# matplotlib.use("pgf")
# matplotlib.rcParams.update({
#     "pgf.texsystem": "pdflatex",
#     'font.family': 'serif',
#     'text.usetex': True,
#     'pgf.rcfonts': False,
# })

oscillator_counts = [2, 4, 6, 8, 10]
inverter_counts = [3, 5, 7, 9, 11]

min_entropy = np.empty(shape=(len(oscillator_counts), len(inverter_counts)))

for osc_idx, osc_count in enumerate(oscillator_counts):
    for inv_idx, inv_count in enumerate(inverter_counts):
        dump = import_module(f'dump_metastable_{osc_count}_{inv_count}')

        metastable = dump.dump["soc_trng_metastable"]

        with NamedTemporaryFile() as fp:
            fp.write(bytes(metastable[::2]))

            process = subprocess.run(['ea_non_iid', '-i', '-a', '-v', fp.name, '1'], 
                                stdout=subprocess.PIPE, 
                                universal_newlines=True)

        pattern = re.compile(r'([^\t]+) Test Estimate = (\d*\.\d+|\d+) / 1 bit\(s\)')
  
        result = {test: float(result) for test, result in re.findall(pattern, process.stdout)}
        print(result)
        del result['tCompression']
        min_entropy[osc_idx][inv_idx] = min(result.values())
        print(f'{osc_count} oscillators with {inv_count} inverters min-entropy: {min(result.values())}')

print(min_entropy)

fig, ax = plt.subplots()
im = ax.imshow(min_entropy, cmap='YlGn')

# We want to show all ticks...
ax.set_xticks(np.arange(len(inverter_counts)))
ax.set_yticks(np.arange(len(oscillator_counts)))
# ... and label them with the respective list entries
ax.set_xticklabels([f'{inv_count} inverters' for inv_count in inverter_counts])
ax.set_yticklabels([f'{osc_count} oscillators' for osc_count in oscillator_counts])

# Rotate the tick labels and set their alignment.
plt.setp(ax.get_xticklabels(), rotation=45, ha="right",
         rotation_mode="anchor")

# Loop over data dimensions and create text annotations.
textcolors = ("black", "white")
threshold = 0.6
for i in range(len(oscillator_counts)):
    for j in range(len(inverter_counts)):
        color = textcolors[int(im.norm(min_entropy[i, j]) > threshold)]
        text = ax.text(j, i, min_entropy[i, j],
                       ha="center", va="center", color=color)

ax.set_title("Harvest of local farmers (in tons/year)")
fig.tight_layout()
plt.show()
#plt.savefig('heatmap.pgf')
