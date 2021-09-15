#!/usr/bin/python3

import sys
import argparse
import math
import textwrap

parser = argparse.ArgumentParser(description='Measure disk read latency vs. write bandwidth')
parser.add_argument('--max-write-bandwidth', type=float, required=True,
                    help='Maximum write bandwidth to test (in B/s)')
parser.add_argument('--max-read-iops', type=float, required=True,
                    help='Maximum read IOPS to test (in ops/s)')
parser.add_argument('--write-test-steps', type=int, default=21,
                    help='Number of subdivisions from 0 to max-write-bandwidth to test')
parser.add_argument('--read-test-steps', type=int, default=21,
                    help='Number of subdivisions from 0 to max-read-iops to test')
parser.add_argument('--read-concurrency', type=int, default=1000)
parser.add_argument('--read-buffer-size', type=int, default=512)
parser.add_argument('--write-concurrency', type=int, default=4)
parser.add_argument('--write-buffer-size', type=int, default=128*1024)
parser.add_argument('--size-limit', type=str, default="0",
                    help='Limit I/O range on device (required for files)')
parser.add_argument('device',
                    help='device to test (e.g. /dev/nmve0n1). Caution: destructive')

args = parser.parse_args()

def generate_job_file(file):
    def out(*args, **kwargs):
        print(*args, **kwargs, file=file)
    out(textwrap.dedent(f'''\
        [global]
        
        runtime=30s
        time_based=1
        startdelay=1s
        filename={args.device}
        direct=1
        group_reporting
        ioengine=io_uring
        size={args.size_limit}
        
        [prepare]
        readwrite=write
        time_based=0
        blocksize=32MB
        iodepth=1

        '''))
    group_introducer=textwrap.dedent('''\
        stonewall
        new_group
        ''')

    for write_bw_step in range(args.write_test_steps):
        write_fraction = write_bw_step / (args.write_test_steps - 1)
        write_bw = int(write_fraction * args.max_write_bandwidth)
        for read_iops_step in range(args.read_test_steps):
            read_fraction = read_iops_step / (args.read_test_steps - 1)
            read_iops = int(math.ceil(read_fraction * args.max_read_iops))
            if read_fraction > 0:
                out(textwrap.dedent(f'''\
                    [read(w={int(write_fraction*100)},r={int(read_fraction*100)})]
                    '''))
                out(group_introducer)
                out(textwrap.dedent(f'''\
                    readwrite=randread
                    blocksize={args.read_buffer_size}
                    iodepth={args.read_concurrency}
                    rate_iops={read_iops}
                    '''))
                write_group_introducer = ''
            else:
                write_group_introducer = group_introducer
            if write_fraction > 0:
                out(textwrap.dedent(f'''\
                    [write(w={int(write_fraction*100)},r={int(read_fraction*100)})]
                    '''))
                out(write_group_introducer)
                out(textwrap.dedent(f'''\
                    readwrite=write
                    blocksize={args.write_buffer_size}
                    iodepth={args.write_concurrency}
                    rate={write_bw}
                    '''))

generate_job_file(file=sys.stdout)

