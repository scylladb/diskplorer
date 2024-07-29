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

Run diskplorer (substitute `/dev/name` with your device file):

```console
sudo ./diskplorer.py /dev/name --result-file your-results.json
```

It is recommended to save the fio test file for later reference (`--fio-job-directory`)

`sudo` is required due to direct disk access.

This will run for several hours. Some smoke may be emitted from the disk.

# Viewing the results

Once done, copy the result file (`test.json`) to your workstation and view the charts with

    ./latency-postprocess.py test.json


# Sample results

## i3en.3xlarge

![i3en.3xlarge chart](latency-matrix-results/i3en.3xlarge.svg)

With 4k blocksize, showing reduction in IOPS due to increased bandwidth demand:

![i3en.3xlarge chart (4k bs)](latency-matrix-results/i3en.3xlarge.bs4k.png)

With 16k blocksize, showing further reduction in IOPS due to increased bandwidth demand:

![i3en.3xlarge chart (16k bs)](latency-matrix-results/i3en.3xlarge.bs16k.png)


## i3.2xlarge

![i3.2xlarge chart](latency-matrix-results/i3.2xlarge.svg)

With additional sequential trim job that discarded 32MB blocks (trim bandwidth == write bandwidth).

![i3.2xlarge chart trim 32MB](latency-matrix-results/i3_2xlarge_trim_block_size_32MB_offset_10s.png)

## im4gn.4xlarge

![im4gn.4xlarge chart](latency-matrix-results/im4gn.4xlarge.png)

## AWS EC2 r5b.2xlarge, EBS GP3 (1000 GB, 1000 MB/s, 16000 IOPS)

![EBS GP3 1000 MB/s, 16000 IOPS](latency-matrix-results/r2b.2xlarge-ebs-gp3-1000g-w1000-r16000.png)

## GCP n2-standard-16, 8 local SSDs in RAID 0

These results are using aio instead of io_uring due to [bad interaction between md and io_uring](https://lore.kernel.org/linux-raid/ee22cbab-950f-cdb0-7ef0-5ea0fe67c628@kernel.dk/).

![n2-standard-16 with 8 local SSDs](latency-matrix-results/gcp-n2-16-8local.png)

## GCP n2-standard-8, 2 TB SSD Persistent Disk

Strangely the 95th percentile at low rates is worse than at high
rates.

![n2-standard-8 with 2TB SSD Persistent Disk](latency-matrix-results/gcp-pd-SSD-2TB.svg)

## Toshiba DT01ACA200 hard disk drive

Results for a rotating hard disk drive. Note the throughput and IOPS were
allows to miss by a 15% margin rather than the normal 3% margin.

![Toshiba DT01ACA200 hard disk drive](latency-matrix-results/hdd-toshiba-DT01ACA200.svg)

