import os


def get_cpu_load() -> str:
    try:
        with open("/proc/loadavg", "r") as f:
            return f.read().split()[0]
    except:
        return "N/A"


def get_mem_usage() -> str:
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].replace(":", "")] = int(parts[1])

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        if total > 0:
            usage = ((total - available) / total) * 100
            return f"{int(usage)}%"
        return "N/A"
    except:
        return "N/A"


def get_battery_info() -> str:
    try:
        base_path = "/sys/class/power_supply/BAT0"
        if not os.path.exists(base_path):
            return "N/A"

        with open(os.path.join(base_path, "capacity"), "r") as f:
            cap = f.read().strip()
        with open(os.path.join(base_path, "status"), "r") as f:
            status = f.read().strip()

        state = "AC" if status == "Charging" else "BAT"
        return f"{cap}%({state})"
    except:
        return "N/A"


def get_wifi_strength() -> str:
    try:
        with open("/proc/net/wireless", "r") as f:
            lines = f.readlines()
            for line in lines:
                if "wlan0" in line:
                    parts = line.split()
                    # Quality link is usually the 3rd column in the wlan0 line
                    quality = parts[2].replace(".", "")
                    # Percentage based on 70 as max (common for linux wireless)
                    # or just return the raw quality if it's simpler
                    return f"{quality}"
        return "N/A"
    except:
        return "N/A"


def get_sys_info():
    return {
        "cpu": get_cpu_load(),
        "mem": get_mem_usage(),
        "bat": get_battery_info(),
        "wifi": get_wifi_strength(),
    }
