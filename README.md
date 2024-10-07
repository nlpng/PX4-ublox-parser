# PX4 ublox gps dump

PX4 has an optional parameter ([`GPS_DUMP_COMM`](https://docs.px4.io/main/en/advanced_config/parameter_reference.html#GPS_DUMP_COMM)) to dump the raw communication of ublox GPS module into the flight log ([ulog](https://docs.px4.io/main/en/dev_log/ulog_file_format.html) format). However the standard log analysis tools do not evaluate this information, for example, [plotjuggler](https://github.com/facontidavide/PlotJuggler), therefore the repo is trying to extract the communication logs of the uBlox GNSS module from the PX4 flight log.

This repo uses `gps_dump` messages that logged by PX4


## Installation
```shell
pip3 install -r requirements.txt
```


## Usage
Run python scripts :
```shell
python3 main.py -i path/to/logfile.ulog
```

Run python scripts with GUI :
```shell
python3 main_gui.py
```

### Parsed messages will be written to:

- logfile_name_MON-RF.csv: Parsed ublox MON-RF messages from the ublox module
- logfile_name_NAV-DOP.csv: Parsed ublox NAV-DOP messages from the ublox module
- logfile_name_NAV-PVT.csv: Parsed ublox NAV-PVT messages from the ublox module


## ublox Protocol Reference
Following ulog protocol messages are extracted. But of course, there are limitations as PX4 does not enable all messages by default. At the moment, we found the `NAV-PVT`, `NAV-DOP`, and `MON-RF` are logged.

```python
MSGATTR = {
    "NAV-PVT": [
        "iTOW",
        "year",
        "month",
        "day",
        "hour",
        "min",
        "second",
        "validDate",
        "validMag",
        "validTime",
        "fullyResolved",
        "tAcc",
        "nano",
        "fixType",
        "gnssFixOk",
        "diffSoln",
        "psmState",
        "headVehValid",
        "carrSoln",
        "numSV",
        "lon",
        "lat",
        "height",
        "hMSL",
        "hAcc",
        "vAcc",
        "velN",
        "velE",
        "velD",
        "gSpeed",
        "headMot",
        "sAcc",
        "headAcc",
        "pDOP",
        "headVeh",
        "magDec",
        "magAcc",
    ],
    "NAV-DOP": ["iTOW", "gDOP", "pDOP", "tDOP", "vDOP", "hDOP", "nDOP", "eDOP"],
    "MON-RF": [
        "version",
        "nBlocks",
        "reserved0",
        {
            "rgroup": (
                "nBlocks",
                [
                    "blockId",
                    "jammingState",
                    "antStatus",
                    "antPower",
                    "postStatus",
                    "reserved1",
                    "noisePerMS",
                    "agcCnt",
                    "jamInd",
                    "ofsI",
                    "magI",
                    "ofsQ",
                    "magQ",
                    "reserved2",
                ],
            )
        },
    ],
    "MON-SYS": [
        "msgVer",
        "bootType",
        "cpuLoad",
        "cpuLoadMax",
        "memUsage",
        "memUsageMax",
        "ioUsage",
        "ioUsageMax",
        "runTime",
        "noticeCount",
        "warnCount",
        "errorCount",
        "tempValue",
        "reserved0",
    ],
}
```
