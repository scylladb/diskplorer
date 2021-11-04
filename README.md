Diskplorer - disk latency/bandwidth grapher
===========================================

Diskplorer is a small set of tools around <code>[fio](https://github.com/axboe/fio)</code> that can be used to discover disk read latency at different read and write workloads. Diskplorer runs a matrix of 21 write workloads (0% to 100% of the maximum bandwidth, in 5% increments) and 21 read workloads (0% to 100% of the maximum IOPS, in 5% increments) for a total of 441 different workloads. The disk is fully written first in order to eliminate clean-disk effects.

Diskplorer runs in two steps: step 1 generates a json result file, and must be run on the system being tested, and step 2 generates latency charts from the result file.


# Running the test

Caution: the test is destructive. Do not use on disks that have real data.

Install the dependencies with

    sudo dnf install -y fio

or

    apt-get install -y fio

Obtain the maximum write bandwith and maximum read IOPS from the device data sheet.

Generate a fio test file (substitute N1, N2, and /dev/name with your device parameters):

    ./read-vs-write-latency.py --max-read-iops N1 --max-write-iops N2 /dev/name > test.fio

It is recommended to save the fio test file for later reference.

Run the fio test with:

    fio --output-format json+ --output test.json test.fio

This will run for several hours. Some smoke may be emitted from the disk.

# Viewing the results

Once done, copy the result file (`test.json`) to your workstation and view the charts with

    ./latency-postprocess.py test.json

# Obsolete diskplorer variant

*Diskplorer* is a small wrapper around <code>[fio](https://github.com/axboe/fio)</code>
that can be used to graph the relationship between concurrency (I/O depth) and
throughput/IOPS.

## Requirements

Diskplorer requires:

1. Python 3
2. python3-matplotlib
3. fio (version 2.0.10 or later)

On Fedora 23, the dependencies can be installed via:

 dnf install python3-matplotlib fio

## Running *diskplorer*
 
Running `diskplorer.py` will create a 100GB test file in the current directory,
and produce a graph named `disk-concurrency-response.svg` in the same place.
The test file is not deleted after a run.

*Diskplorer* also support the following command-line options:


    -h, --help            show this help message and exit
    -d MOUNTPOINT, --mountpoint=MOUNTPOINT
                          Test disk mounted at MOUNTPOINT
    -b DEV, --device=DEV  Test block device DEV (overrides --mountpoint)
    -s SIZE, --filesize=SIZE
                          Set SIZE as file size for test
    -m N, --max-concurrency=N
                          Test maximum concurrency level N
    -o FILE, --output=FILE
                          Write output graph to FILE

## Example results

Here are results on a fairly good NVMe SSD.  At its peak, the drive is delivering 1.8GB/sec.

![Example results](example-results/monster.png)

