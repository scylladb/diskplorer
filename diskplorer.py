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
parser.add_argument('--read-buffer-size', type=int, default=None)
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

if dev_major == 9:
    # 'md' doesn't support io_uring well yet
    ioengine = 'libaio'

print(dev_major, dev_minor, dev_path, ioengine)

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
    delay = None
    def global_section():
        out(textwrap.dedent(f'''\
            [global]
        
            runtime={args.test_step_time_seconds}s
            time_based=1
            filename={args.device}
            direct=1
            group_reporting
            ioengine={ioengine}
            size={args.size_limit}
            random_generator=tausworthe64
            randrepeat=0
            thread

        '''))
    if args.prefill is None or args.prefill:
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
        delay = 15
        run(file)
        
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
            read_iops = max(read_iops, 1)   # no point in a write-only test
            nr_cpus = args.cpus
            startdelay = f'startdelay={delay}s' if delay else ''
            delay = None
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
