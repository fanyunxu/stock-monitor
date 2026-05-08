from fastapi import APIRouter
import psutil
import socket
import os

router = APIRouter(prefix="/api/system", tags=["system"])


def get_cpu_model():
    """Get CPU model name from /proc/cpuinfo."""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return None


def get_memory_slots():
    """Get number of memory slots via dmidecode (requires root/sudo).
    Falls back to: total GB + slot count estimate."""
    try:
        import subprocess
        result = subprocess.run(
            ['sudo', 'dmidecode', '-t', '16'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            count = result.stdout.count('Memory Device')
            if count > 0:
                return count
    except Exception:
        pass
    # Fallback: psutil doesn't expose slot count, return None
    return None


def get_cpu_temp():
    """Get CPU temperature. Returns None if not available."""
    try:
        temps = psutil.sensors_temperatures()
        for name, entries in temps.items():
            for entry in entries:
                if entry.current is not None:
                    return round(entry.current, 1)
    except Exception:
        pass
    return None


def get_memory_info():
    """Get memory usage info."""
    mem = psutil.virtual_memory()
    slots = get_memory_slots()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
        "slots": slots
    }


def get_disk_info():
    """Get disk usage info with model/vendor."""
    # Build a map of mountpoint -> physical device model from /proc/mounts
    mount_model_map = {}
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    device = parts[0]
                    mountpoint = parts[1]
                    dev_name = device.replace('/dev/', '').strip()
                    # Try block device model
                    for name in [dev_name, f'sda', f'sdb']:
                        model_path = f'/sys/block/{name}/device/model'
                        if os.path.exists(model_path):
                            try:
                                with open(model_path, 'r') as mf:
                                    mount_model_map[mountpoint] = mf.read().strip()
                                    break
                            except Exception:
                                pass
    except Exception:
        pass

    partitions = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            device_info = {"device": part.device, "mountpoint": part.mountpoint, "fstype": part.fstype}
            device_info["model"] = mount_model_map.get(part.mountpoint)
            device_info.update({
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent
            })
            partitions.append(device_info)
        except PermissionError:
            continue
        except Exception:
            continue
    return partitions


@router.get("/info")
def system_info():
    """Get all system info."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_model = get_cpu_model()
    memory = get_memory_info()
    disks = get_disk_info()
    cpu_temp = get_cpu_temp()

    hostname = socket.gethostname()

    return {
        "hostname": hostname,
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "count_logical": cpu_count_logical,
            "model": cpu_model,
            "temperature_c": cpu_temp
        },
        "memory": memory,
        "disks": disks
    }