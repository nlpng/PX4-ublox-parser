import csv
import os
import struct
import sys
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog

from pyubx2 import UBXReader
from pyulog.core import ULog

from ubx_interface import CLIDPAIR_INV, MSGATTR, SYNC1, SYNC2, UbxParserState


class tkinterGUI:
    def __init__(self) -> None:
        root = tk.Tk()
        root.attributes("-topmost", True)
        root.title("PX4 gps_dump parser")
        root.geometry("400x400+50+100")

        frame_grid = tk.Frame(root, relief=tk.GROOVE, borderwidth=2)
        frame_grid.pack(side=tk.TOP)

        frame_file = tk.Frame(frame_grid)

        frame_file.grid(column=0, row=0, padx=5, pady=5)

        butn_select = tk.Button(
            frame_file,
            text="ULog Select",
            command=self.select_dialog,
            bg="#2196f3"
        )
        butn_select.pack(side=tk.LEFT, padx=10)

        self.cap_filename = tk.StringVar()
        textbox_cap = tk.Entry(
            frame_file,
            textvariable=self.cap_filename, width=30
        )
        textbox_cap.pack(side=tk.LEFT, padx=10)

        # abs path to .ulog
        self.ulog_abs_path = None

        separator = ttk.Separator(frame_grid, orient="horizontal")
        separator.grid(column=0, row=1, sticky="ew")

        frame_pack = tk.Frame(root, relief=tk.GROOVE, borderwidth=2)
        frame_pack.pack(side=tk.TOP, pady=5)

        butn_parser = tk.Button(
            frame_pack, text="GO", command=self.start_parser, bg="#2196f3"
        )
        butn_parser.pack(side=tk.LEFT, padx=10)

        log_label = tk.Label(frame_pack, text="OUTPUT")
        log_label.pack(side=tk.LEFT, padx=5)

        self.logbox = tk.Text(frame_pack, width=40, height=35)
        self.logbox.pack(side=tk.TOP)

        root.mainloop()

    def parsing(self):
        """Parsing gps_dump msgs and save to csv"""
        output_file_prefix = os.path.basename(self.ulog_abs_path)
        # strip ".ulog"
        if output_file_prefix.lower().endswith(".ulg"):
            output_file_prefix = output_file_prefix[:-4]

        raw_msgs = self.extract_gps_dump(self.ulog_abs_path)

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
                        parsed_msg = UBXReader.parse(
                            bytes(data[: 6 + payload_len + 2])
                        )

                    except Exception as e:
                        print(e)
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

    def extract_gps_dump(self, ulog_filename):
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

    def start_parser(self):
        if self.ulog_abs_path is None:
            self.pprint("File not valid!")
            return

        self.pprint(f"Parsing {os.path.basename(self.ulog_abs_path)} file")
        self.parsing()

    def select_dialog(self):
        path = os.path.abspath(os.path.dirname(__file__))
        cap_filepath = filedialog.askopenfilename(initialdir=path)
        self.ulog_abs_path = cap_filepath

        filename = os.path.basename(cap_filepath)
        self.cap_filename.set(filename)

    def pprint(self, str):
        self.logbox.insert(tk.END, str + "\n")
        self.logbox.see(tk.END)


if __name__ == "__main__":
    gps_dump_parser = tkinterGUI()
