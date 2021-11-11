#!/usr/bin/python3

import json
import numpy as np
import re
import collections
import argparse
import matplotlib
import matplotlib.pyplot as plt
import itertools

parser = argparse.ArgumentParser(description='Post-process latency matrix results')
parser.add_argument('file',
                    help='JSON result file from fio')
parser.add_argument('--output',
                    help='Output file (.svg/.png) (default=interactive)')

args = parser.parse_args()

cell = collections.namedtuple('cell', ['r_iops', 'w_bw', 'r_clat'])

for result_file in [args.file]:
    jobs = json.load(open(result_file))['jobs']

    results_dict = {}

    for j in jobs:
        name = j['jobname']
        if name == 'prepare':
            continue
        m = re.match(r'job\(r_idx=(\d+),w_idx=(\d+),write_bw=(\d+),r_iops=(\d+)', name)
        r_idx, w_idx, w_bw, r_iops = [int(x) for x in m.groups()]
        results_dict[(r_idx, w_idx)] = cell(r_iops=r_iops, w_bw=w_bw, r_clat=j['read']['clat_ns'])

n_r = max([k[0] for k in results_dict.keys()]) + 1
n_w = max([k[1] for k in results_dict.keys()]) + 1

shape = [n_w, n_r]

p50 = np.zeros(shape)
p95 = np.zeros(shape)        
r_iops = np.zeros(shape)
w_bw = np.zeros(shape)
        
for key, cell in results_dict.items():
    r_iops[key[1]][key[0]] = cell.r_iops
    w_bw[key[1]][key[0]] = cell.w_bw
    if 'percentile' in cell.r_clat:
        p50[key[1]][key[0]] = float(cell.r_clat['percentile']['50.000000']) * 1e-6
        p95[key[1]][key[0]] = float(cell.r_clat['percentile']['95.000000']) * 1e-6


mats = [
    ('p50', p50),
    ('p95', p95),
]

matplotlib.rcParams.update({
    'font.size': 9,
    'figure.figsize': (12, 8),
})


fig, axs = plt.subplots(2)

for name_mat, ax in zip(mats, axs):
    name, mat = name_mat
    ax.set_title(f'{name} latency')
    ax.set_xlabel('w_bw')
    ax.set_ylabel('r_iops')
    c = ax.pcolor(w_bw, r_iops, mat, shading='auto', cmap='cool',
                  norm=matplotlib.colors.Normalize(vmin=0, vmax=5, clip=True))
    fig.colorbar(c, ax=ax)


if args.output:
    fig.savefig(args.output, dpi=600)
else:
    fig.show()
    plt.pause(100)
