import argparse
import csv
import os
import struct
import sys

from pyubx2 import UBXReader
from pyulog.core import ULog

from ubx_interface import CLIDPAIR_INV, MSGATTR, SYNC1, SYNC2, UbxParserState


def extract_gps_dump(ulog_filename):
    """Get gps dump data"""
    # looking into gps_dump
    msg_filter = ["gps_dump"]
    ulog = ULog(ulog_filename, msg_filter, disable_str_exceptions=False)
    data = ulog.data_list

    if len(data) == 0:
        print(f"File {ulog_filename} does not have necessary msgs")
        sys.exit(0)

    if len(ulog.dropouts) > 0:
        print(f"File has {ulog.dropouts} dropouts")

    for d in data:
        print(f"Found {len(d.field_data)} msgs in {d.name}")

    gps_dump_data = data[0]
    field_names = [f.field_name for f in gps_dump_data.field_data]
    if "len" not in field_names or "data[0]" not in field_names:
        print("gps dump: msgs are not correct")
        sys.exit(-1)

    msg_lens = gps_dump_data.data["len"]
    print(f"gps_dump msg lens {len(msg_lens)}")

    parser_state = UbxParserState.IDLE

    synced_msgs = {}
    msg_buffer = []
    for i in range(len(gps_dump_data.data["timestamp"])):
        for d in range(79):
            data_byte = gps_dump_data.data["data[{}]".format(d)][i]

            if parser_state == UbxParserState.IDLE:
                msg_buffer = []
                if data_byte == SYNC1:
                    parser_state = UbxParserState.SYNC

            elif parser_state == UbxParserState.SYNC:
                msg_buffer = []
                if data_byte == SYNC2:
                    msg_buffer.append(SYNC1)
                    msg_buffer.append(SYNC2)
                    parser_state = UbxParserState.READING

            elif parser_state == UbxParserState.READING:
                if data_byte == SYNC1 and d + 1 < 79:
                    next_data_byte = gps_dump_data.data["data[{}]".format(d + 1)][i]
                    if next_data_byte == SYNC2:
                        synced_msgs[i] = (
                            msg_buffer,
                            gps_dump_data.data["timestamp"][i],
                        )
                        parser_state = UbxParserState.SYNC
                    else:
                        msg_buffer.append(data_byte)

                elif (
                    data_byte == SYNC1
                    and d == 78
                    and i + 1 < len(gps_dump_data.data["timestamp"])
                ):
                    # last index in gps_dump data, look into next batch
                    next_data_byte = gps_dump_data.data["data[{}]".format(0)][i + 1]
                    if next_data_byte == SYNC2:
                        synced_msgs[i] = (
                            msg_buffer,
                            gps_dump_data.data["timestamp"][i],
                        )
                        parser_state = UbxParserState.SYNC
                    else:
                        msg_buffer.append(data_byte)
                else:
                    msg_buffer.append(data_byte)

    return synced_msgs


def main():
    parser = argparse.ArgumentParser(description="PX4 uBlox Communication Analyzer")
    parser.add_argument(
        "-i",
        "--input_filename",
        action="store",
        required=True,
        help="path to input file (output will be named similar)",
    )
    args = parser.parse_args()

    if not args.input_filename:
        ulog_filename = "log_160_2024-10-4-14-27-46.ulg"
    else:
        ulog_filename = args.input_filename

    output_file_prefix = os.path.basename(ulog_filename)
    # strip ".ulog"
    if output_file_prefix.lower().endswith(".ulg"):
        output_file_prefix = output_file_prefix[:-4]

    raw_msgs = extract_gps_dump(ulog_filename)

    count_msgs = dict()
    valid_msgs = dict()
    for _, msg in raw_msgs.items():
        if len(msg[0]) == 2:
            # somehow only contains preamble 1 and preamble 2
            continue

        data = msg[0]
        timestamp = msg[1]
        if data[0] == SYNC1 and data[1] == SYNC2:
            (cls, id, payload_len) = struct.unpack("<BBH", bytes(data[2:6]))
            clid = CLIDPAIR_INV.get((cls, id))
            if clid:
                try:
                    # 6 bytes (sync1, sync2, class, id, len1, len2)
                    # 2 bytes (checksum)
                    parsed_msg = UBXReader.parse(bytes(data[: 6 + payload_len + 2]))

                except Exception as e:
                    print(e)
                    # print(f"len: {payload_len}, {len(data[: 6 + payload_len + 2])}")
                    continue

                if clid in count_msgs:
                    count_msgs[clid] += 1
                else:
                    count_msgs[clid] = 1

                entries = []
                header = []
                try:
                    for item in MSGATTR[clid]:
                        if isinstance(item, dict) and "rgroup" in item:
                            rep_attr, rep_entries = item["rgroup"]
                            n_rep = getattr(parsed_msg, rep_attr)
                            for r in range(int(n_rep)):
                                for r_entry in rep_entries:
                                    attr_name = r_entry + f"_{r + 1:02}"
                                    entries.append(getattr(parsed_msg, attr_name))
                                    header.append(attr_name)
                        else:
                            entries.append(getattr(parsed_msg, item))
                            header.append(item)

                    if clid not in valid_msgs:
                        valid_msgs[clid] = dict(timestamp=header)
                        valid_msgs[clid][timestamp] = entries
                        # valid_msgs[clid] = {timestamp: entries}
                    else:
                        valid_msgs[clid][timestamp] = entries

                except Exception:
                    continue

    print(f"gps_dump contains following messages \n{count_msgs}")
    # print(valid_msgs)

    for k, v in valid_msgs.items():
        output_filename = output_file_prefix + f"_{k}.csv"
        csv_fields = ["timestamp"] + v.get("timestamp")

        with open(output_filename, mode="w", newline="") as csv_entry:
            csv_writer = csv.writer(csv_entry, delimiter=",")
            csv_writer.writerow(csv_fields)

            for t, entry in v.items():
                if t == "timestamp":
                    continue
                csv_writer.writerow([t] + list(entry))


if __name__ == "__main__":
    main()
