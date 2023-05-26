import time
import requests
import psutil
import subprocess
import platform
import re
import os
import json
import logging
from datetime import datetime
from multiprocessing import Process, Pool, Queue
import configparser
from systemd.journal import JournalHandler


def get_disk():
    """Get disk partition information

    Returns:
        list: list of partition's information
    """
    logger.debug("Enter function (get_disk)")
    partition_table = []
    disk_info = psutil.disk_partitions()
    while disk_info:
        device, mountpoint, fstype, *other = disk_info.pop()
        total, used, free, percent = psutil.disk_usage(mountpoint)
        partition_table.append({
            "device": device,
            "mountpoint": mountpoint,
            "fstype": fstype,
            "total": total,
            "used": used,
            "free": free,
            "usedPercent": round(used / total * 100, 2)
        })
    return partition_table


def get_osinfo(p_data):
    """Get OS information

    Args:
        p_data (dict): The performance information
        {"cpu": xx.xx, "mem": xx.xx, "swap": xx.xx}

    Returns:
        dict: Post data
    """
    logger.debug("Enter function (get_osinfo)")
    # UUID field is from /etc/machine-id file, but this file can be changed, should use another file that can't be changed.
    uuid = subprocess.Popen(
        ['cat', '/etc/machine-id'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()[0].decode('utf-8').replace(
            "\n", "")
    result = {
        # Example: 2023-04-10 15:27:37
        "datetime":
        datetime.now().isoformat(' ', timespec='seconds'),
        "host_info": {
            # FQDN
            "hostname": platform.uname().node.lower(),
            # xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx -> xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
            "hostId":
            f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}",
            "uptime": int(datetime.now().timestamp() - psutil.boot_time()),
            "bootTime": int(psutil.boot_time()),
            # Example: Rocky Linux
            "os": platform.freedesktop_os_release().get('NAME'),
            # Example: 8.7
            "platformVersion":
            platform.freedesktop_os_release().get('VERSION_ID'),
            # 4.18.0-425.3.1.el8.x86_64
            "kernelVersion": platform.release(),
            # x86_64
            "kernelArch": platform.machine()
        },
        "cpu_count":
        len(os.sched_getaffinity(0)),
        "cpu_usage":
        float(format(p_data.get("cpu"), '.2f')),
        "memory_usage":
        float(format(p_data.get("mem"), '.2f')),
        "swap_usage":
        float(format(p_data.get("swap"), '.2f')),
        # disk usage about / partition
        "disk_usage": [
            x.get('usedPercent') for x in get_disk()
            if x.get('mountpoint') == '/'
        ][0],
        "disk_partitions":
        get_disk(),
    }
    logger.debug(f"Post Data: {json.dumps(result)}")
    return result


def perform_monitor(q, avg_interval):
    """Get Performance Data

    Args:
        q (Queue): Queue
        avg_interval (int): The performance interval

    """
    logger.debug("Enter function (get_disk)")
    result = {"cpu": 0, "mem": 0, "swap": 0}
    count = 0
    while True:
        if count == avg_interval:
            result["cpu"] /= avg_interval
            result["mem"] /= avg_interval
            result["swap"] /= avg_interval
            q.put(result)
            result = {"cpu": 0, "mem": 0, "swap": 0}
            count = 0
        result["mem"] += (psutil.virtual_memory().available /
                          psutil.virtual_memory().total) * 100
        result["cpu"] += psutil.cpu_percent()
        result["swap"] += (psutil.swap_memory().used /
                           psutil.swap_memory().total) * 100
        count += 1
        time.sleep(1)


def main():
    CONF_PATH = "/etc/sysmo-agent/sysmo-agent.conf"
    try:
        AGENT_CONF_PARSER = configparser.RawConfigParser()
        AGENT_CONF_PARSER.read(CONF_PATH)
        perform_interval = int(AGENT_CONF_PARSER.get('Interval', 'Perform'))
        host = AGENT_CONF_PARSER.get('Server', 'Host')
        port = AGENT_CONF_PARSER.get('Server', 'Port')
    except:
        logger.error("Please check the sysmo-agent.conf.")
    logger.debug(f"interval: {perform_interval}, host: {host}, port: {port}")
    q = Queue()
    perf_p = Process(target=perform_monitor,
                     args=(q, perform_interval),
                     name="Performance Monitor")
    perf_p.start()

    headers = {'content-type': 'application/json'}
    while True:
        p_data = q.get()
        try:
            response = requests.post(f"http://{host}:{port}/post_log/",
                                     data=json.dumps(get_osinfo(p_data)),
                                     headers=headers)
            logger.info(
                f"status: {response.status_code}, interval: {response.headers['refresh_time_interval']}"
            )
            if int(response.headers['refresh_time_interval']) != int(
                    perform_interval):
                with open("/etc/sysmo-agent/sysmo-agent.conf", 'r+') as f:
                    data = f.read()
                    data = re.sub(
                        f"Perform = {perform_interval}",
                        f"Perform = {response.headers['refresh_time_interval']}",
                        data)
                    f.seek(0)
                    f.write(data)
                    f.truncate()
                    perform_interval = response.headers[
                        'refresh_time_interval']
                    os._exit(1)
        except requests.exceptions.ConnectionError:
            logger.error(
                "Connection refused. Please check the status of Sysmo Server.")


if __name__ == '__main__':
    LOG_PATH = "/var/log/sysmo-agent/agent.log"
    DEBUG = False
    logging.basicConfig(
        filename=LOG_PATH,
        format='%(asctime)s %(levelname)s %(threadName)s : %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(__name__)
    JOURNALD_HANDLER = JournalHandler()  # SYSLOG_IDENTIFIER='sysmo-agent')
    JOURNALD_HANDLER.setFormatter(
        logging.Formatter('%(levelname)s : %(message)s'))
    logger.addHandler(JOURNALD_HANDLER)
    logger.setLevel(logging.INFO if DEBUG is False else logging.DEBUG)
    main()
