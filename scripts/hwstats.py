"""Read HWiNFO64's shared-memory sensor block (Global\\HWiNFO_SENS_SM2) and print the
numbers that matter while a run is going: CPU package temp, per-core temps, CPU load,
package power, fan RPM, RAM used, GPU temp, drive temps. HWiNFO must be running with
'Shared Memory Support' enabled (Settings -> HWiNFO64 -> Shared Memory Support).

    python scripts/hwstats.py            # one snapshot
    python scripts/hwstats.py 60 90      # every 60 s for 90 minutes, appended to data/hwstats.csv

Layout from the HWiNFO SDK (HWiNFO_SENSORS_SHARED_MEM2): header 'HWiS', then arrays of
sensor and reading elements at the offsets the header gives.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import csv
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "Global\\HWiNFO_SENS_SM2"
FILE_MAP_READ = 0x0004
HDR = struct.Struct("<4sIIqIIIIII")             # sig, version, revision, poll_time, sensor_off, sensor_size, n_sensors, reading_off, reading_size, n_readings
READING = struct.Struct("<IIIi128s128s16sdddd")   # type, sensor_idx, id, instance, label_orig, label_user, unit, value, min, max, avg
TYPES = {0: "none", 1: "temp", 2: "volt", 3: "fan", 4: "current", 5: "power", 6: "clock", 7: "usage", 8: "other"}

k32 = ctypes.windll.kernel32
k32.OpenFileMappingW.restype = wt.HANDLE
k32.MapViewOfFile.restype = ctypes.c_void_p


def read_all():
    h = k32.OpenFileMappingW(FILE_MAP_READ, False, NAME)
    if not h:
        raise RuntimeError("HWiNFO shared memory not found - is HWiNFO running with Shared Memory Support enabled?")
    view = k32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, 0)
    try:
        head = ctypes.string_at(view, HDR.size)
        sig, ver, rev, poll, s_off, s_size, n_s, r_off, r_size, n_r = HDR.unpack(head)
        if sig != b"HWiS":
            raise RuntimeError(f"bad signature {sig!r}")
        out = []
        for i in range(n_r):
            raw = ctypes.string_at(view + r_off + i * r_size, READING.size)
            typ, sidx, rid, inst, lo, lu, unit, val, mn, mx, avg = READING.unpack(raw)
            label = (lu.split(b"\0")[0] or lo.split(b"\0")[0]).decode("utf-8", "ignore")
            out.append({"type": TYPES.get(typ, str(typ)), "label": label, "unit": unit.split(b"\0")[0].decode("utf-8", "ignore"),
                        "value": val, "min": mn, "max": mx, "avg": avg})
        return out
    finally:
        k32.UnmapViewOfFile(ctypes.c_void_p(view)); k32.CloseHandle(h)


def pick(rows):
    """The handful of readings a person wants to see, by label (as HWiNFO names them)."""
    want = {}
    for r in rows:
        lab, t = r["label"], r["type"]
        if t == "temp" and ("CPU Package" in lab or lab in ("CPU (Tctl/Tdie)", "CPU Die (average)", "Core Temperatures")):
            want["cpu_pkg_c"] = r["value"]
        if t == "temp" and lab.startswith("Core") and "Max" not in lab and "Distance" not in lab:
            want.setdefault("cores_c", []).append(round(r["value"], 1))
        if t == "usage" and lab in ("Total CPU Usage", "CPU Usage"):
            want["cpu_load_pct"] = r["value"]
        if t == "power" and lab in ("CPU Package Power", "CPU Package"):
            want["cpu_pkg_w"] = r["value"]
        if t == "fan":
            want.setdefault("fans_rpm", {})[lab] = round(r["value"])
        if t == "usage" and lab == "Physical Memory Load":
            want["ram_used_pct"] = r["value"]
        if t == "other" and lab == "Physical Memory Used":
            want["ram_used_mb"] = r["value"]
        if t == "temp" and "GPU" in lab and "Hot" not in lab and "Memory" not in lab:
            want.setdefault("gpu_c", r["value"])
        if t == "temp" and ("Drive" in lab or "SSD" in lab or "NVMe" in lab):
            want.setdefault("drives_c", {})[lab] = round(r["value"], 1)
        if t == "other" and "Thermal Throttling" in lab:
            want.setdefault("throttling", {})[lab] = r["value"]
    return want


def main():
    every = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    end = time.time() + minutes * 60
    path = ROOT / "data" / "hwstats.csv"
    first = True
    while True:
        rows = read_all(); w = pick(rows)
        line = (f"{datetime.now():%H:%M:%S}  CPU {w.get('cpu_pkg_c')}C pkg {w.get('cpu_pkg_w')}W load {w.get('cpu_load_pct')}%  "
                f"cores {w.get('cores_c')}  RAM {w.get('ram_used_pct')}% ({w.get('ram_used_mb')} MB)  fans {w.get('fans_rpm')}  "
                f"GPU {w.get('gpu_c')}C  drives {w.get('drives_c')}  throttling {w.get('throttling')}")
        print(line, flush=True)
        if every:
            with open(path, "a", newline="") as f:
                wr = csv.writer(f)
                if first and path.stat().st_size == 0:
                    wr.writerow(["time", "cpu_pkg_c", "cpu_pkg_w", "cpu_load_pct", "ram_used_pct", "ram_used_mb", "cores_c", "fans_rpm", "gpu_c", "drives_c"])
                wr.writerow([datetime.now().isoformat(timespec="seconds"), w.get("cpu_pkg_c"), w.get("cpu_pkg_w"), w.get("cpu_load_pct"),
                             w.get("ram_used_pct"), w.get("ram_used_mb"), w.get("cores_c"), w.get("fans_rpm"), w.get("gpu_c"), w.get("drives_c")])
            first = False
        if not every or time.time() >= end:
            break
        time.sleep(every)
    if "--all" in sys.argv:
        for r in rows:
            print(f"{r['type']:7} {r['label'][:48]:48} {r['value']:>12.2f} {r['unit']}")


if __name__ == "__main__":
    main()
