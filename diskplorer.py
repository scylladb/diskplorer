#!/usr/bin/python3

import sys
import argparse
import math
import textwrap
import multiprocessing
import subprocess
import tempfile
import json
import os
import stat
import time

parser = argparse.ArgumentParser(description='Measure disk read latency vs. write bandwidth')
parser.add_argument('--prefill', action='store_true',
                    help='Prefill entire disk, defeats incorrect results due to discard (default)')
parser.add_argument('--no-prefill', action='store_false', dest='prefill',
                    help='Skips prefill')
parser.set_defaults(prefill=None)
parser.add_argument('--max-write-bandwidth', type=float,
                    help='Maximum write bandwidth to test (in B/s) (default=auto-discover)')
parser.add_argument('--max-read-iops', type=float,
                    help='Maximum read IOPS to test (in ops/s) (default=auto-discover)')
parser.add_argument('--write-test-steps', type=int, default=20,
                    help='Number of subdivisions from 0 to max-write-bandwidth to test')
parser.add_argument('--read-test-steps', type=int, default=20,
                    help='Number of subdivisions from 0 to max-read-iops to test')
parser.add_argument('--test-step-time-seconds', type=int, default=30,
                    help='Time to run each step')
parser.add_argument('--read-concurrency', type=int, default=1000)
parser.add_argument('--read-buffer-size', type=int, default=None)
parser.add_argument('--write-concurrency', type=int, default=64)
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

if args.fio_job_directory and not os.path.exists(args.fio_job_directory):
    os.makedirs(args.fio_job_directory)

def generate_job_names(group_name):
    idx = 0
    while True:
        yield group_name + (f'.{idx}' if idx > 0 else '')
        idx += 1

ioengine = 'io_uring'
dev_stat = os.stat(args.device)
dev_minor = None
dev_major = None
dev_path = None
if stat.S_ISBLK(dev_stat.st_mode):
    dev_major = os.major(dev_stat.st_rdev)
    dev_minor = os.minor(dev_stat.st_rdev)
    dev_path = f'/sys/dev/block/{dev_major}:{dev_minor}'
    try:
        partition = int(open(f'{dev_path}/partition').read())
        dev_path = f'/sys/dev/block/{dev_major}:{dev_minor-partition}'
    except:
        pass
    args.read_buffer_size = args.read_buffer_size or int(open(f'{dev_path}/queue/logical_block_size').read())
else:
    dev_major = None
    dev_minor = None
    dev_path = None
    args.read_buffer_size = args.read_buffer_size or 512

args.write_concurrency = min(args.write_concurrency, int(open(f'{dev_path}/queue/nr_requests').read()))

if dev_major == 9:
    # 'md' doesn't support io_uring well yet
    ioengine = 'libaio'

if args.prefill is None:
    args.prefill = not bool(int(open(f'{dev_path}/queue/rotational').read()))

# split `count` things among `among` users. Tries to be as
# fair as possible. Returns an iterator. Doesn't bother
# splitting below 'dont_bother_below'
def split_among(count, among, dont_bother_below=1):
    while count > 0:
        this_count = max(int(math.ceil(count / among)), min(dont_bother_below, count))
        yield this_count
        count -= this_count
        among -= 1
    
def run_jobs():
    def job_files():
        counter = 0
        while True:
            if args.fio_job_directory:
                job_file_name = f'{args.fio_job_directory}/{counter:04}.fio'
                counter += 1
                yield open(job_file_name, 'w')
            else:
                yield tempfile.NamedTemporaryFile(mode='w')
    files = job_files()
    def run(job_file):
        job_file.flush()
        tmp_json = tempfile.NamedTemporaryFile()
        subprocess.check_call(['fio', '--output-format=json+', '--output', tmp_json.name, job_file.name])
        this_job_results = json.load(open(tmp_json.name))
        return this_job_results
    file = None
    def out(*args, **kwargs):
        print(*args, **kwargs, file=file)
    def global_section():
        out(textwrap.dedent(f'''\
            [global]
        
            runtime={args.test_step_time_seconds}s
            time_based=1
            ramp_time=5
            filename={args.device}
            direct=1
            group_reporting
            ioengine={ioengine}
            size={args.size_limit}
            random_generator=tausworthe64
            randrepeat=0
            thread

        '''))
    if args.prefill:
        file = next(files)
        global_section()
        out(textwrap.dedent(f'''\
            [prepare]
            readwrite=write
            time_based=0
            blocksize=2MB
            iodepth=4
            runtime=0

            '''))
        time.sleep(15)
        run(file)

    if args.max_write_bandwidth is None:
        file = next(files)
        global_section()
        out(textwrap.dedent(f'''\
            [max-write-bw]
            readwrite=write
            blocksize={args.write_buffer_size}
            iodepth={args.write_concurrency}
            '''))
        write_bw_json = run(file)
        job = write_bw_json['jobs'][0]
        args.max_write_bandwidth = job['write']['bw_bytes']
        time.sleep(10)

    if args.max_read_iops is None:
        # we don't know what concurrency yields the best result, so measure it
        concurrency = 15
        max_iops = 0
        while concurrency < 1024:
            file = next(files)
            global_section()
            nr = 0
            group_introducer = 'new_group'
            for this_cpu_concurrency in split_among(concurrency, args.cpus):
                out(textwrap.dedent(f'''\
                    [max-read-iops-{concurrency}-{nr}]
                    readwrite=randread
                    blocksize={args.read_buffer_size}
                    iodepth={this_cpu_concurrency}
                    {group_introducer}
                    '''))
                group_introducer = ''
                nr += 1
            read_bw_json = run(file)
            job = read_bw_json['jobs'][0]
            iops = job['read']['iops']
            if iops < max_iops:
                break
            max_iops = iops
            concurrency = 2*concurrency + 1
        args.max_read_iops = max_iops
        
    group_introducer=textwrap.dedent('''\
        stonewall
        new_group
        ''')

    for write_bw_step in range(args.write_test_steps + 1):
        write_fraction = write_bw_step / args.write_test_steps
        write_bw = int(write_fraction * args.max_write_bandwidth)
        for read_iops_step in range(args.read_test_steps + 1):
            file = next(files)
            global_section()

            read_fraction = read_iops_step / args.read_test_steps
            read_iops = int(math.ceil(read_fraction * args.max_read_iops))
            job_names = generate_job_names(f'job(r_idx={read_iops_step},w_idx={write_bw_step},write_bw={write_bw},r_iops={read_iops})')
            read_iops = max(read_iops, 10)   # no point in a write-only test
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
            for this_cpu_read_iops in split_among(read_iops, nr_cpus, 10):
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
                    rate_process=poisson
                    '''))
            yield run(file)

results = None

for this_job_results in run_jobs():
    if this_job_results is None:
        continue
    if results is None:
        results = this_job_results
    else:
        results['jobs'].extend(this_job_results['jobs'])

json.dump(results, open(args.result_file, 'w'))
