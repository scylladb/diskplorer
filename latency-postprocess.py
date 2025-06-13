#!/usr/bin/python3

import json
import numpy as np
import re
import collections
import argparse
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker
import itertools

parser = argparse.ArgumentParser(description='Post-process latency matrix results',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                 )
parser.add_argument('file',
                    help='JSON result file from fio')
parser.add_argument('--output',
                    help='Output file (.svg/.png) (default=interactive)')
parser.add_argument('--write-throughput-allowed-error', type=float, default=0.03,
                    help='Allowed error in write throughput below which the results are not admissible')
parser.add_argument('--read-iops-allowed-error', type=float, default=0.03,
                    help='Allowed error in read throughput below which the results are not admissible')
parser.add_argument('--p99-and-p999', action='store_true',
                    help='Plots P99 and P999 instead of P50 and P95')
parser.set_defaults(p99_and_p999=False)

args = parser.parse_args()

cell = collections.namedtuple('cell', ['r_iops', 'w_bw', 'r_clat',
                                       'actual_w_bw', 'actual_r_iops'])

for result_file in [args.file]:
    jobs = json.load(open(result_file))['jobs']

    results_dict = {}

    for j in jobs:
        name = j['jobname']
        if name == 'prepare' or name.startswith('prepare_data_for_trim'):
            continue
        m = re.match(r'job\(r_idx=(\d+),w_idx=(\d+),write_bw=(\d+),r_iops=(\d+)', name)
        r_idx, w_idx, w_bw, r_iops = [int(x) for x in m.groups()]
        results_dict[(r_idx, w_idx)] = cell(r_iops=r_iops, w_bw=w_bw,
                                            r_clat=j['read']['clat_ns'],
                                            actual_w_bw=int(j['write']['bw_bytes']),
                                            actual_r_iops=int(j['read']['iops'])
                                            )

n_r = max([k[0] for k in results_dict.keys()]) + 1
n_w = max([k[1] for k in results_dict.keys()]) + 1

shape = [n_w, n_r]

p50 = np.ma.array(np.zeros(shape), mask=True)
p95 = np.ma.array(np.zeros(shape), mask=True)
p99 = np.ma.array(np.zeros(shape), mask=True)
p999 = np.ma.array(np.zeros(shape), mask=True)

r_iops = np.zeros(shape)
w_bw = np.zeros(shape)
        
for key, cell in results_dict.items():
    r_iops[key[1]][key[0]] = cell.r_iops
    w_bw[key[1]][key[0]] = cell.w_bw
    if (cell.actual_w_bw < (1 - args.write_throughput_allowed_error) * cell.w_bw
        or cell.actual_r_iops < (1 - args.read_iops_allowed_error) * cell.r_iops):
        continue
    if 'percentile' in cell.r_clat:
        p50[key[1]][key[0]] = float(cell.r_clat['percentile']['50.000000']) * 1e-6
        p95[key[1]][key[0]] = float(cell.r_clat['percentile']['95.000000']) * 1e-6
        p99[key[1]][key[0]] = float(cell.r_clat['percentile']['99.000000']) * 1e-6
        p999[key[1]][key[0]] = float(cell.r_clat['percentile']['99.900000']) * 1e-6

if args.p99_and_p999:
    mats = [
        ('p99', p99),
        ('p999', p999),
    ]
else:
    mats = [
        ('p50', p50),
        ('p95', p95),
    ]

min_latency = np.amin(p50)

matplotlib.rcParams.update({
    'font.size': 9,
    'figure.figsize': (12, 8),
})


fig, axs = plt.subplots(2)

for name_mat, ax in zip(mats, axs):
    name, mat = name_mat
    ax.set_title(f'{name} latency')
    ax.set_xlabel('w_bw')
    ax.xaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='B/s'))
    ax.set_ylabel('r_iops')
    ax.yaxis.set_major_formatter(matplotlib.ticker.EngFormatter(unit='op/s'))
    c = ax.pcolor(w_bw, r_iops, mat, shading='auto', cmap='cool',
                  norm=matplotlib.colors.LogNorm(vmin=min_latency, 
                                                 vmax=min_latency*50,
                                                 clip=True))
    colorbar = fig.colorbar(c, ax=ax)
    colorbar.set_label('latency (ms)')

if args.output:
    fig.savefig(args.output, dpi=600)
else:
    fig.show()
    plt.pause(100)
