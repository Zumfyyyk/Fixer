import eel
import os
import psutil
import subprocess
import glob
import json
import winreg
import logging
import platform
import shutil
from datetime import datetime
import time
import GPUtil
import socket
import requests
from packaging import version
import ctypes

eel.init('web')

APP_VERSION = "1.0"
CONFIG_FILE = "config.json"

def setup_logger():
    """Настройка логирования в файл."""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(
        filename=f'logs/fixer_{datetime.now().strftime("%Y%m%d")}.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

setup_logger()

def log_action(action, status="success", message=""):
    """Запись действия в лог."""
    logging.info(f"{action} - {status.upper()}: {message}")

def load_config():
    """Загрузка конфигурации приложения."""
    default_config = {
        "theme": "dark",
        "language": "ru",
        "notifications": True,
        "sound": True,
        "start_minimized": False,
        "checkUpdatesOnStart": False,
        "tray": False,
        "autorun": False
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return {**default_config, **json.load(f)}
        return default_config
    except Exception as e:
        log_action("Load config", "error", str(e))
        return default_config

def save_config(config):
    """Сохранение конфигурации приложения."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        log_action("Save config", "error", str(e))
        return False

@eel.expose
def get_system_info():
    """Получение информации о системе."""
    try:
        import wmi
        cpu_name = ""
        try:
            w = wmi.WMI()
            for cpu in w.Win32_Processor():
                cpu_name = cpu.Name.strip()
                break
        except Exception:
            cpu_name = platform.processor()
        # Оставляем только модель (без семейства и лишнего)
        import re
        match = re.search(r'(Intel|AMD)[^@,]+', cpu_name)
        cpu_model = match.group(0).strip() if match else cpu_name.split('@')[0].strip()
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "architecture": platform.architecture()[0],
            "processor": cpu_model,
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "ram": round(psutil.virtual_memory().total / (1024 ** 3), 2)
        }
    except Exception as e:
        log_action("Get system info", "error", str(e))
        return {}

@eel.expose
def toggle_service(service_name, state):
    """Включение/отключение службы Windows."""
    try:
        action = "start" if state else "stop"
        result = subprocess.run(
            f"net {action} {service_name}",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if result.returncode == 0:
            log_action(f"Service {service_name} toggle", "success", f"Set to {state}")
            return {"success": True, "message": f"Служба {service_name} {'включена' if state else 'выключена'}"}
        else:
            error_msg = result.stderr.strip() or "Неизвестная ошибка"
            log_action(f"Service {service_name} toggle", "error", error_msg)
            return {"success": False, "message": f"Ошибка: {error_msg}"}
    except Exception as e:
        log_action(f"Service {service_name} toggle", "error", str(e))
        return {"success": False, "message": f"Ошибка: {str(e)}"}

@eel.expose
def get_services():
    """Получение статуса рекомендуемых служб."""
    services = [
        {
            "name": "SysMain",
            "displayName": "SysMain (Superfetch)",
            "description": "Предзагрузка часто используемых приложений в RAM. Отключение может снизить нагрузку на диск.",
            "enabled": False
        },
        {
            "name": "wuauserv",
            "displayName": "Windows Update (Центр обновления Windows)",
            "description": "Фоновая проверка и установка обновлений. Отключение освобождает ресурсы, но есть риск упустить критические обновления.",
            "enabled": False
        },
        {
            "name": "WSearch",
            "displayName": "Windows Search",
            "description": "Индексация файлов для быстрого поиска. Часто грузит диск. На слабых ПК — отключение оправдано.",
            "enabled": False
        },
        {
            "name": "DiagTrack",
            "displayName": "Connected User Experiences and Telemetry (Диагностика и телеметрия)",
            "description": "Сбор диагностических данных и отправка в Microsoft. Безопасно отключается.",
            "enabled": False
        },
        {
            "name": "Fax",
            "displayName": "Fax",
            "description": "Поддержка отправки/приема факсов. Полностью бесполезна на обычных ПК.",
            "enabled": False
        },
        {
            "name": "RemoteRegistry",
            "displayName": "Remote Registry",
            "description": "Разрешает удалённые изменения реестра. Потенциальная уязвимость.",
            "enabled": False
        },
        {
            "name": "seclogon",
            "displayName": "Secondary Logon",
            "description": "Позволяет запуск программ от имени другого пользователя. Можно отключать.",
            "enabled": False
        },
        {
            "name": "WerSvc",
            "displayName": "Windows Error Reporting Service",
            "description": "Отправка отчетов об ошибках в Microsoft. Безопасно отключается.",
            "enabled": False
        },
        {
            "name": "Spooler",
            "displayName": "Print Spooler (Диспетчер печати)",
            "description": "Поддержка печати. Не нужен, если принтеры не используются.",
            "enabled": False
        },
        {
            "name": "TabletInputService",
            "displayName": "Touch Keyboard and Handwriting Panel Service",
            "description": "Поддержка экранной клавиатуры и распознавания почерка. Полезна только на планшетах.",
            "enabled": False
        },
        {
            "name": "bthserv",
            "displayName": "Bluetooth Support Service",
            "description": "Поддержка Bluetooth-устройств. Не нужен, если Bluetooth не используется.",
            "enabled": False
        }
    ]
    try:
        for service in services:
            result = subprocess.run(
                f"sc query {service['name']}",
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            service["enabled"] = "RUNNING" in result.stdout
        return services
    except Exception as e:
        log_action("Get services", "error", str(e))
        return services

@eel.expose
def toggle_firewall(enable):
    """Включение/отключение брандмауэра Windows."""
    try:
        state = "on" if enable else "off"
        result = subprocess.run(
            f"netsh advfirewall set allprofiles state {state}",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        if result.returncode == 0:
            log_action("Firewall toggle", "success", f"Set to {state}")
            return {"success": True, "message": f"Брандмауэр {'включен' if enable else 'выключен'}"}
        else:
            error_msg = result.stderr.strip() or "Неизвестная ошибка"
            log_action("Firewall toggle", "error", error_msg)
            return {"success": False, "message": f"Ошибка: {error_msg}"}
    except Exception as e:
        log_action("Firewall toggle", "error", str(e))
        return {"success": False, "message": f"Ошибка: {str(e)}"}

@eel.expose
def get_firewall_status():
    """Проверяет состояние брандмауэра Windows."""
    try:
        result = subprocess.run(
            'netsh advfirewall show allprofiles',
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        enabled = "State ON" in result.stdout or "Состояние ВКЛ" in result.stdout
        return {"enabled": enabled}
    except Exception as e:
        log_action("Get firewall status", "error", str(e))
        return {"enabled": False}

def get_cache_paths():
    """Возвращает словарь путей к кэшу популярных приложений."""
    paths = {}
    # Chrome
    chrome_path = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache")
    if os.path.exists(chrome_path):
        paths["Chrome"] = chrome_path
    # Edge
    edge_path = os.path.expanduser("~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache")
    if os.path.exists(edge_path):
        paths["Edge"] = edge_path
    # Firefox
    firefox_profiles = glob.glob(os.path.expanduser("~\\AppData\\Local\\Mozilla\\Firefox\\Profiles\\*.default-release"))
    if firefox_profiles:
        paths["Firefox"] = os.path.join(firefox_profiles[0], "cache2")
    # Discord
    discord_path = os.path.expanduser("~\\AppData\\Roaming\\discord\\Cache")
    if os.path.exists(discord_path):
        paths["Discord"] = discord_path
    # Temp
    temp_path = os.path.expanduser("~\\AppData\\Local\\Temp")
    if os.path.exists(temp_path):
        paths["Temp"] = temp_path
    # Prefetch
    prefetch_path = os.path.expandvars("%SystemRoot%\\Prefetch")
    if os.path.exists(prefetch_path):
        paths["Prefetch"] = prefetch_path
    # RecycleBin (не показываем в списке кэша)
    return paths

@eel.expose
def get_cache_sizes():
    """Возвращает размеры кэша для поддерживаемых приложений."""
    paths = get_cache_paths()
    sizes = {}
    for name, path in paths.items():
        try:
            total_size = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except:
                        pass
            sizes[name] = round(total_size / (1024 ** 2), 2)
        except Exception as e:
            sizes[name] = 0
            log_action(f"Get {name} cache size", "error", str(e))
    return sizes

@eel.expose
def clear_cache(app_name):
    """Очищает кэш выбранного приложения."""
    try:
        paths = get_cache_paths()
        path = None
        if app_name == "Firefox":
            profiles_path = paths.get("Firefox")
            if profiles_path:
                firefox_profiles = glob.glob(os.path.join(profiles_path, "*.default-release"))
                if firefox_profiles:
                    path = os.path.join(firefox_profiles[0], "cache2")
        else:
            path = paths.get(app_name)
        if path and os.path.exists(path):
            deleted = 0
            total_size = 0
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted += 1
                        total_size += file_size
                    except:
                        pass
            mb_freed = round(total_size / (1024 ** 2), 2)
            log_action(f"Clear {app_name} cache", "success", f"Deleted {deleted} files, freed {mb_freed} MB")
            return {
                "success": True,
                "message": f"Кэш {app_name} очищен",
                "details": f"Удалено {deleted} файлов, освобождено {mb_freed} MB"
            }
        return {"success": False, "message": "Путь не найден"}
    except Exception as e:
        log_action(f"Clear {app_name} cache", "error", str(e))
        return {"success": False, "message": str(e)}

@eel.expose
def quick_clean():
    """Быстрая очистка всех поддерживаемых кэшей."""
    try:
        paths = get_cache_paths()
        total_deleted = 0
        total_freed = 0
        results = []
        for name, path in paths.items():
            if name == "Firefox":
                profiles_path = path
                firefox_profiles = glob.glob(os.path.join(profiles_path, "*.default-release"))
                if firefox_profiles:
                    path = os.path.join(firefox_profiles[0], "cache2")
            if os.path.exists(path):
                deleted = 0
                size_freed = 0
                for root, dirs, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted += 1
                            size_freed += file_size
                        except:
                            pass
                if deleted > 0:
                    total_deleted += deleted
                    total_freed += size_freed
                    mb_freed = round(size_freed / (1024 ** 2), 2)
                    results.append(f"{name}: {deleted} файлов, {mb_freed} MB")
        if total_deleted > 0:
            total_mb = round(total_freed / (1024 ** 2), 2)
            log_action("Quick clean", "success", f"Deleted {total_deleted} files, freed {total_mb} MB")
            return {
                "success": True,
                "message": "Быстрая очистка завершена",
                "details": f"Всего удалено {total_deleted} файлов, освобождено {total_mb} MB",
                "results": results
            }
        else:
            return {"success": True, "message": "Нечего очищать", "details": "Все кэши уже чистые"}
    except Exception as e:
        log_action("Quick clean", "error", str(e))
        return {"success": False, "message": str(e)}

@eel.expose
def empty_recycle_bin():
    """Очищает корзину Windows."""
    try:
        if platform.system() == "Windows":
            import ctypes
            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI = 0x00000002
            SHERB_NOSOUND = 0x00000004
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
            if result == 0:
                log_action("Empty recycle bin", "success")
                return {"success": True, "message": "Корзина очищена"}
            else:
                log_action("Empty recycle bin", "error", f"Code {result}")
                return {"success": False, "message": f"Ошибка очистки корзины (код {result})"}
        else:
            return {"success": False, "message": "Операция поддерживается только в Windows"}
    except Exception as e:
        log_action("Empty recycle bin", "error", str(e))
        return {"success": False, "message": str(e)}

@eel.expose
def get_stats():
    """Получение статистики системы (CPU, RAM, диски, сеть, GPU, температура)."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disks = []
        for part in psutil.disk_partitions():
            if 'cdrom' in part.opts or part.fstype == '':
                continue
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            })
        net_io = psutil.net_io_counters()
        gpu_info = []
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_info.append({
                    "name": gpu.name,
                    "load": gpu.load * 100,
                    "memory_used": gpu.memoryUsed,
                    "memory_total": gpu.memoryTotal,
                    "temperature": gpu.temperature
                })
        except:
            pass
        cpu_temp = get_cpu_temperature()
        return {
            'cpu': {
                'percent': cpu_percent,
                'cores': psutil.cpu_count(logical=False),
                'threads': psutil.cpu_count(logical=True),
                'freq': {
                    'current': cpu_freq.current if cpu_freq else 0,
                    'max': cpu_freq.max if cpu_freq else 0
                }
            },
            'ram': {
                'total': ram.total,
                'available': ram.available,
                'used': ram.used,
                'percent': ram.percent
            },
            'swap': {
                'total': swap.total,
                'used': swap.used,
                'percent': swap.percent
            },
            'disks': disks,
            'network': {
                'sent': net_io.bytes_sent,
                'recv': net_io.bytes_recv,
                'speed': get_network_speed()
            },
            'gpu': gpu_info[0] if gpu_info else None,
            'temperature': {
                'cpu': cpu_temp
            },
            'timestamp': time.time()
        }
    except Exception as e:
        log_action("Get stats", "error", str(e))
        return {}

def get_cpu_temperature():
    """Пытается получить температуру CPU (только Windows с OpenHardwareMonitor)."""
    try:
        if platform.system() == "Windows":
            import wmi
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            for sensor in w.Sensor():
                if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
                    return sensor.Value
        elif platform.system() == "Linux":
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.read()) / 1000
        return 0
    except:
        return 0

def get_network_speed():
    """Измеряет скорость передачи данных за 1 секунду."""
    try:
        net1 = psutil.net_io_counters()
        time.sleep(1)
        net2 = psutil.net_io_counters()
        return {
            'sent': (net2.bytes_sent - net1.bytes_sent) / 1024,
            'recv': (net2.bytes_recv - net1.bytes_recv) / 1024
        }
    except:
        return {'sent': 0, 'recv': 0}

@eel.expose
def get_startup_apps():
    """Получение списка программ автозагрузки."""
    apps = []
    try:
        # Current User
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, value, _ = winreg.EnumValue(key, i)
                apps.append({
                    "name": name,
                    "path": value,
                    "enabled": True,
                    "type": "user"
                })
        # Local Machine
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, value, _ = winreg.EnumValue(key, i)
                apps.append({
                    "name": name,
                    "path": value,
                    "enabled": True,
                    "type": "system"
                })
        return apps
    except Exception as e:
        log_action("Get startup apps", "error", str(e))
        return apps

@eel.expose
def toggle_startup_app(app_name, app_type, enable):
    """Включение/отключение приложения автозагрузки (не удаляет)."""
    try:
        if app_type == "user":
            root = winreg.HKEY_CURRENT_USER
        else:
            root = winreg.HKEY_LOCAL_MACHINE
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        access = winreg.KEY_SET_VALUE | winreg.KEY_READ
        with winreg.OpenKey(root, reg_path, 0, access) as reg_key:
            if enable:
                # Для примера: путь к exe должен быть передан с фронта!
                # Здесь просто ничего не делаем, если уже есть
                pass
            else:
                try:
                    winreg.DeleteValue(reg_key, app_name)
                except FileNotFoundError:
                    pass
        log_action("Toggle startup app", "success", f"{app_name} set to {enable}")
        return True
    except Exception as e:
        log_action("Toggle startup app", "error", str(e))
        return False

@eel.expose
def delete_startup_app(app_name, app_type):
    """Удаление приложения из автозагрузки."""
    try:
        if app_type == "user":
            root = winreg.HKEY_CURRENT_USER
        else:
            root = winreg.HKEY_LOCAL_MACHINE
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        access = winreg.KEY_SET_VALUE | winreg.KEY_READ
        with winreg.OpenKey(root, reg_path, 0, access) as reg_key:
            try:
                winreg.DeleteValue(reg_key, app_name)
            except FileNotFoundError:
                pass
        log_action("Delete startup app", "success", app_name)
        return True
    except Exception as e:
        log_action("Delete startup app", "error", str(e))
        return False

@eel.expose
def set_autorun(enable):
    """Включить/отключить автозапуск Fixer при старте Windows."""
    try:
        exe_path = os.path.abspath(__file__)
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Fixer"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'python "{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
        log_action("Set autorun", "success", f"Set to {enable}")
        return True
    except Exception as e:
        log_action("Set autorun", "error", str(e))
        return False

@eel.expose
def get_config():
    """Получить текущую конфигурацию."""
    return load_config()

@eel.expose
def update_config(new_config):
    """Обновить конфигурацию."""
    current_config = load_config()
    updated_config = {**current_config, **new_config}
    if save_config(updated_config):
        return {"success": True, "message": "Настройки сохранены"}
    else:
        return {"success": False, "message": "Ошибка сохранения настроек"}

@eel.expose
def check_updates():
    """Проверка наличия обновлений на GitHub."""
    try:
        response = requests.get(
            "https://api.github.com/repos/zumfyyyk/fixer/releases/latest",
            timeout=5
        )
        if response.status_code == 200:
            latest_version = response.json()["tag_name"]
            if version.parse(latest_version) > version.parse(APP_VERSION):
                return {
                    "update_available": True,
                    "latest_version": latest_version,
                    "current_version": APP_VERSION,
                    "release_url": response.json()["html_url"]
                }
        return {"update_available": False}
    except Exception as e:
        log_action("Check updates", "error", str(e))
        return {"update_available": False, "error": str(e)}

@eel.expose
def get_locale(lang='ru'):
    """Получить локализацию для выбранного языка."""
    try:
        with open('web/locales.json', 'r', encoding='utf-8') as f:
            locales = json.load(f)
        return locales.get(lang, locales['ru'])
    except Exception as e:
        log_action("Get locale", "error", str(e))
        return {}

def start():
    """Запуск eel-приложения."""
    try:
        try:
            is_admin = os.getuid() == 0 if platform.system() != "Windows" else ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            is_admin = False
        if not is_admin:
            log_action("Start app", "warning", "Running without admin privileges")
        eel.start('main.html',
                  size=(1200, 800),
                  mode='chrome',
                  position=(100, 100),
                  disable_cache=True)
    except Exception as e:
        log_action("Start app", "error", str(e))

if __name__ == '__main__':
    log_action("Application started", "info", f"Version {APP_VERSION}")
    start()
