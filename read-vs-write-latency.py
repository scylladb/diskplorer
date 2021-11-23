#!/usr/bin/python3

import sys
import argparse
import math
import textwrap
import multiprocessing
import subprocess
import tempfile
import json

parser = argparse.ArgumentParser(description='Measure disk read latency vs. write bandwidth')
parser.add_argument('--prefill', action='store_true',
                    help='Prefill entire disk, defeats incorrect results due to discard (default)')
parser.add_argument('--no-prefill', action='store_false', dest='prefill',
                    help='Skips prefill')
parser.add_argument('--max-write-bandwidth', type=float, required=True,
                    help='Maximum write bandwidth to test (in B/s)')
parser.add_argument('--max-read-iops', type=float, required=True,
                    help='Maximum read IOPS to test (in ops/s)')
parser.add_argument('--write-test-steps', type=int, default=20,
                    help='Number of subdivisions from 0 to max-write-bandwidth to test')
parser.add_argument('--read-test-steps', type=int, default=20,
                    help='Number of subdivisions from 0 to max-read-iops to test')
parser.add_argument('--test-step-time-seconds', type=int, default=30,
                    help='Time to run each step')
parser.add_argument('--read-concurrency', type=int, default=1000)
parser.add_argument('--read-buffer-size', type=int, default=512)
parser.add_argument('--write-concurrency', type=int, default=4)
parser.add_argument('--write-buffer-size', type=int, default=128*1024)
parser.add_argument('--size-limit', type=str, default="0",
                    help='Limit I/O range on device (required for files)')
parser.add_argument('--cpus', type=int, default=multiprocessing.cpu_count(),
                    help='Number of processors to use (default=all)')
parser.add_argument('device',
                    help='device to test (e.g. /dev/nmve0n1). Caution: destructive')
parser.add_argument('--fio-job-directory', type=str,
                    help='Directory to place fio job files (default: files will not be kept)')
parser.add_argument('--result-file', type=str, required=True,
                    help='Results, in fio json+ format')

args = parser.parse_args()

def generate_job_names(group_name):
    idx = 0
    while True:
        yield group_name + (f'.{idx}' if idx > 0 else '')
        idx += 1

def generate_job_file(file):
    def out(*args, **kwargs):
        print(*args, **kwargs, file=file)
    out(textwrap.dedent(f'''\
        [global]
        
        runtime={args.test_step_time_seconds}s
        time_based=1
        startdelay=1s
        filename={args.device}
        direct=1
        group_reporting
        ioengine=io_uring
        size={args.size_limit}
        random_generator=tausworthe64
        thread

        '''))
    if args.prefill is None or args.prefill:
        out(textwrap.dedent(f'''\
            [prepare]
            readwrite=write
            time_based=0
            blocksize=2MB
            iodepth=4
            runtime=0

            '''))
    group_introducer=textwrap.dedent('''\
        stonewall
        new_group
        ''')

    for write_bw_step in range(args.write_test_steps + 1):
        write_fraction = write_bw_step / args.write_test_steps
        write_bw = int(write_fraction * args.max_write_bandwidth)
        for read_iops_step in range(args.read_test_steps + 1):
            read_fraction = read_iops_step / args.read_test_steps
            read_iops = int(math.ceil(read_fraction * args.max_read_iops))
            job_names = generate_job_names(f'job(r_idx={read_iops_step},w_idx={write_bw_step},write_bw={write_bw},r_iops={read_iops})')
            read_iops = max(read_iops, 1)   # no point in a write-only test
            nr_cpus = args.cpus
            if write_bw > 0:
                out(textwrap.dedent(f'''\
                    [{next(job_names)}]
                    '''))
                out(group_introducer)
                out(textwrap.dedent(f'''\
                    readwrite=write
                    blocksize={args.write_buffer_size}
                    iodepth={args.write_concurrency}
                    rate={write_bw}
                    '''))
                nr_cpus -= 1
                read_group_introducer = ''
            else:
                read_group_introducer = group_introducer
            while read_iops > 0:
                this_cpu_read_iops = int(math.ceil(read_iops / nr_cpus))
                read_iops -= this_cpu_read_iops
                nr_cpus -= 1
                out(textwrap.dedent(f'''\
                    [{next(job_names)}]
                    '''))
                out(read_group_introducer)
                read_group_introducer = ''
                out(textwrap.dedent(f'''\
                    readwrite=randread
                    blocksize={args.read_buffer_size}
                    iodepth={args.read_concurrency}
                    rate_iops={this_cpu_read_iops}
                    '''))

if args.fio_job_directory:
    job_file_name = f'{args.fio_job_directory}/0000.fio'
    job_file = open(job_file_name, 'w')
else:
    job_file = tempfile.NamedTemporaryFile(mode='w')
    job_file_name = job_file.name

generate_job_file(file=job_file)
job_file.flush()

def run_job(job_file_name):
    tmp_json = tempfile.NamedTemporaryFile()
    subprocess.check_call(['fio', '--output-format=json+', '--output', tmp_json.name, job_file_name])
    return json.load(open(tmp_json.name))

results = run_job(job_file_name)

json.dump(results, open(args.result_file, 'w'))
