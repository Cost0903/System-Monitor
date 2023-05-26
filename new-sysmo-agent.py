import time
import requests
import psutil
import subprocess
import platform
import uuid
import asyncio
import tracemalloc
import re
import os, sys
import json
from memory_profiler import profile
import logging
from socket import AddressFamily
from random import random
import multiprocessing
from datetime import datetime
from multiprocessing import Process, Pool, Pipe, Queue
import configparser
from systemd.journal import JournalHandler


class Machine:
    """The information about registered machine.
    """

    def __init__(self) -> None:
        self.uuid = self.get_uuid()
        self.hostname = platform.uname().node.lower()
        self.cpu = self.CPU()
        self.mem = self.Memory()
        # Specific interface or All interfaces (Use All interfaces by now)
        self.net = self.NIC()
        # Container Disk information needs to be carefully.
        self.disk = self.Disk()
        # OS Information: Linux, Windows, etc.
        self.os = platform.uname().system
        self.release = platform.release()

    def __str__(self) -> str:
        return self.hostname.lower()

    @staticmethod
    def get_uuid():  # need root permission, change to /etc/machine-id
        """Getting system UUID information depending on dmidecode command.

        Returns:
            str: UUID value.
        """
        # Use system uuid in dmidcode
        uuid = subprocess.Popen(
            ['sudo', 'dmidecode', '-s', 'system-uuid'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[0].decode('utf-8').replace(
                "\n", "")
        return uuid

    class CPU:
        """CPU information
        """
        INTERVAL = 5

        def __init__(self) -> None:
            self.core = psutil.cpu_count()
            self.socket = psutil.cpu_count(logical=False)
            self.thread = self.core / self.socket

        # @profile
        @staticmethod
        def get_perf(interval=INTERVAL):
            return psutil.cpu_percent(interval=interval)

    class Memory:
        """Memroy information
        """
        AVG_INTERVAL = 1
        INTERVAL = 5

        def __init__(self) -> None:
            self.size = ""  # Total memory that the system has.
            self.count = ""  # The memory sticks amount.

        def get_perf(self, interval=INTERVAL, avg_interval=AVG_INTERVAL):
            result = 0
            for i in range(0, interval, avg_interval):
                result += 100 - ((psutil.virtual_memory().available /
                                  psutil.virtual_memory().total) * 100)
            return result / (interval / avg_interval)

    class NIC:
        """Network information
        """

        addrs = psutil.net_if_addrs()

        def __init__(self) -> None:
            addrs = self.format_NIC()
            print(type(addrs))
            # json.loads(addrs)
            self.name = [key for key, value in addrs.items()]
            self.ipv4 = [value["ipv4"] for key, value in addrs.items()]
            # [None if not value["ipv6"] else value["ipv6"] for key, value in addrs.items()]
            self.ipv6 = ""
            self.mac = [value["mac"] for key, value in addrs.items()]

        def __str__(self):
            return f"Name: {self.name}\nIPv4: {self.ipv4}\nIPv6: {self.ipv6}\nMac: {self.mac}"

        def check_type(self, net: AddressFamily) -> str:
            """Check the address of type from interface

            Args:
                net (AddressFamily): The interface adress information

            Returns:
                str: The type of address
            """
            type_dict = {
                AddressFamily.AF_INET: "ipv4",
                AddressFamily.AF_INET6: "ipv6",
                AddressFamily.AF_PACKET: "mac"
            }
            return type_dict.get(net)

        def format_NIC(self):
            interface_info = {}
            addrs = psutil.net_if_addrs()
            # if_type = []
            for key, value in addrs.items():  # key is interface name
                if key != 'lo':
                    interface_detail = {}
                    for i in value:
                        interface_detail[self.check_type(
                            i.family)] = i.address if self.check_type(
                                i.family) != "ipv6" else re.sub(
                                    r"%.*", "", i.address)
                    interface_info.update({key: interface_detail})
            return interface_info

    # class Disk:
    #     """Disk information
    #     """

    #     def __init__(self) -> None:
    #         self.pt = self.Partition()  # Mount Point
    #         self.size = ""
    #         self.type = ""  # Disk Type
    #         self.name = ""  # Disk Name

    #     def __str__(self):
    #         return f"Name: {self.name}\nSize: {self.size}\nType: {self.type}"

    #     def list_partitions(self):
    #         """List all the partitions

    #         Returns:
    #             list: List of partitions
    #         """
    #         return [x.device for x in psutil.disk_partitions()]

    class Partition():
        """Partition information
        """

        def __init__(self) -> None:
            # self.table = {}
            self.table = []
            disk_info = psutil.disk_partitions()
            while disk_info:  # opts, maxfile, maxpath
                device, mountpoint, fstype, *other = disk_info.pop()
                # used, free, percent
                total, *other = psutil.disk_usage(mountpoint)
                total, used, free, percent = psutil.disk_usage(mountpoint)
                # self.table[device] = {
                #     "mountpoint": mountpoint,
                #     "fstype": fstype,
                #     "total": total,
                #     "used": used,
                #     "free": free,
                #     "usedPercent": round(used / total * 100, 2)
                #     # "usedPercent": percent
                # }
                self.table.append({
                    "device": device,
                    "mountpoint": mountpoint,
                    "fstype": fstype,
                    "total": total,
                    "used": used,
                    "free": free,
                    "usedPercent": round(used / total * 100, 2)
                    # "usedPercent": percent
                })


def get_osinfo(p_data):
    """Get OS information

    Returns:
        dict: OS information
    """
    # print(Machine.Partition().table)
    uuid = subprocess.Popen(
            ['cat', '/etc/machine-id'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[0].decode('utf-8').replace(
                "\n", "")
    result = {
        "datetime":
        datetime.now().isoformat(' ', timespec='seconds'),
        "host_info": {
            # platform.uname().node.lower() + str(int(random() * 100)),
            "hostname": platform.uname().node.lower(),
            "hostId":
            f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}",  # c40a22c11bf34b99aa67df16c1869cf1
            "uptime": int(datetime.now().timestamp() - psutil.boot_time()),
            "bootTime": int(psutil.boot_time()),
            "os": "Linux",
            # "platform": "",
            # "platformFamily": "",
            "platformVersion": "8.7",
            # "kernelVersion": "",
            # "kernelArch": ""
        },
        "cpu_count":
        len(os.sched_getaffinity(0)),
        "cpu_usage":
        float(format(p_data.get("cpu"), '.2f')),
        "memory_usage":
        float(format(p_data.get("mem"), '.2f')),
        "swap_usage":
        float(format(p_data.get("swap"), '.2f')),
        "disk_usage": [
            x.get('usedPercent') for x in Machine.Partition().table
            if x.get('mountpoint') == '/'
        ][0],
        # "network_info": Machine.NIC().format_NIC(),
        "disk_partitions":
        Machine.Partition().table,
    }
    # print(result)
    return result


def perform_monitor(q, avg_interval):
    result = {"cpu": 0, "mem": 0, "swap": 0}
    count = 0
    # avg_interval = 3
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


def info():
    print(f"module name: {__name__}")
    print(f"parent process: {os.getppid()}")
    print(f"process ID: {os.getpid()}")


def cpu_perf(q, interval):
    # print(time.time())
    info()
    while True:
        # collect(1, time.time(), psutil.cpu_percent(interval=int(interval)))
        # print(
        #     f"time: {time.time()} cpu: {psutil.cpu_percent(interval=int(interval))}"
        # )
        q.put(
            f"time: {time.time()} cpu: {psutil.cpu_percent(interval=int(interval))}"
        )


def mem_perf(q, interval, avg_interval):
    info()
    result = count = 0
    while True:
        if count == 3:
            # collect(2, time.time(), (result / avg_interval))
            # print(f"time: {time.time()} mem: {result / avg_interval}")
            q.put(f"time: {time.time()} memory: {result / avg_interval}")
            result = count = 0
        # print(f"mem_time: {time.time()} count: {count}")
        result += (psutil.virtual_memory().available /
                   psutil.virtual_memory().total) * 100
        # print(f"mem: {result}")
        count += 1
        time.sleep(interval)


def swap_perf(q, interval, avg_interval):
    info()
    result = count = 0
    while True:
        if count == 3:
            q.put(f"time: {time.time()} swap: {result / avg_interval}")
            result = count = 0
        result += (psutil.swap_memory().used /
                   psutil.swap_memory().total) * 100
        count += 1
        time.sleep(interval)


def disk_perf(q, interval, avg_interval):
    info()
    disk_table = {}
    disk_usage = np.array([])
    result = count = 0
    while True:
        disk_info = psutil.disk_partitions()
        mountpoint = [x.mountpoint for x in disk_info]

        if count == 3:
            disk_usage = disk_usage.reshape(avg_interval, len(mountpoint))
            # print(disk_usage.sum(axis=0) / 3)
            q.put(
                f"time: {time.time()} disk: {dict(zip(mountpoint, disk_usage.sum(axis=0) / 3))}"
            )
            count = 0
            disk_usage = np.array([])
        for m in mountpoint:
            disk_usage = np.append(
                disk_usage,
                (psutil.disk_usage(m).used / psutil.disk_usage(m).total) * 100)
            # print(disk_table)
            # try:
            #     disk_table[m] += (psutil.disk_usage(m).used /
            #                       psutil.disk_usage(m).total) * 100
            # except:
            #     disk_table[m] = (psutil.disk_usage(m).used /
            #                      psutil.disk_usage(m).total) * 100
            # if count == 3:
            #     disk_table[m] = disk_table[m] / avg_interval

        #     q.put(f"time: {time.time()} disk: {disk_table}")
        count += 1
        time.sleep(interval)


# @profile
def main():
    CONF_PATH = "/etc/sysmo-agent/sysmo-agent.conf"
    AGENT_CONF_PARSER = configparser.RawConfigParser()
    AGENT_CONF_PARSER.read(CONF_PATH)
    perform_interval = int(AGENT_CONF_PARSER.get('Interval', 'Perform'))
    host = AGENT_CONF_PARSER.get('Server', 'Host')
    port = AGENT_CONF_PARSER.get('Server', 'Port')
    # logging.info(f"interval: {perform_interval}\nhost: {host}\nport: {port}")
    # mem_interval = 1
    # swap_interval = 1
    # disk_interval = 1
    # cpu_avg_interval = 3
    # mem_avg_interval = 3
    # swap_avg_interval = 3
    # disk_avg_interval = 3
    q = Queue()
    # pool = Pool(1)
    perf_p = Process(target=perform_monitor,
                     args=(q, perform_interval),
                     name="Performance Monitor")
    perf_p.start()

    # pool = Pool(4)
    # cpu_p = Process(target=cpu_perf,
    #                 args=(q, cpu_avg_interval),
    #                 name="CPU_monitor")
    # mem_p = Process(target=mem_perf,
    #                 args=(q, mem_interval, mem_avg_interval),
    #                 name="MEM_monitor")
    # swap_p = Process(target=swap_perf,
    #                  args=(q, swap_interval, swap_avg_interval),
    #                  name="SWAP_monitor")

    # disk_p = Process(target=disk_perf,
    #                  args=(q, disk_interval, disk_avg_interval),
    #                  name="DISK_monitor")

    # cpu_p.start()
    # mem_p.start()
    # swap_p.start()
    # disk_p.start()
    # collect_p = Process(target=collect, args=(q, ), name="Collect")
    # tracemalloc.start()
    # m = Machine()
    # print(
    #     f"hostname: {m}\nuuid: {m.uuid}\ncpu: {m.cpu.get_perf()}\nmem: {m.mem.get_perf()}\n{m.net}\ndisk: {m.disk}\nos: {m.os}\nrelease: {m.release}"
    # )
    # ruuid = uuid.getnode()

    # print(get_osinfo(p_data))
    # print(json.dumps(get_osinfo(p_data)))

    headers = {'content-type': 'application/json'}
    while True:
        print("---")
        p_data = q.get()
        print(p_data)
        try:
            # print("try")
            response = requests.post(
                f"http://{host}:{port}/post_log/",
                # response = requests.post('http://192.168.1.138/logserver/machines/',
                data=json.dumps(get_osinfo(p_data)),
                #  auth=('cost', '1qaz@WSX'),
                headers=headers)
            print(f"status: {response.status_code}, Perform: {perform_interval} ,interval: {response.headers['refresh_time_interval']}")
            # logging.info(f"status: {response.status_code}, interval: {response.headers['refresh_time_interval']}")
            logger.info(f"status: {response.status_code}, interval: {response.headers['refresh_time_interval']}")
            if int(response.headers['refresh_time_interval']) != int(perform_interval):
                print()
                with open("/etc/sysmo-agent/sysmo-agent.conf", 'r+') as f:
                    data = f.read()
                    data = re.sub(f"Perform = {perform_interval}", f"Perform = {response.headers['refresh_time_interval']}", data)
                    f.seek(0)
                    f.write(data)
                    f.truncate()
                    perform_interval = response.headers['refresh_time_interval']
                    os._exit(1)
                    # print("join")
                    # print(perf_p.is_alive())
                    # perf_p.kill()
                    # print(perf_p.is_alive())
                    # perf_p.join()
                    # perf_p.close()
                    # # print(perf_p.is_alive())
                    # print("start")
                    # q = Queue()
                    # # pool = Pool(1)
                    # perf_p1 = Process(target=perform_monitor, args=(q, perform_interval), name="Performance Monitor")
                    # perf_p1.start()
                    # print(perf_p1.is_alive())
                    # print("end")
                    # perf_p.join()
                # fin = open("/etc/sysmo-agent/sysmo-agent.conf", 'rt')

                # data = fin.read()
                # data = data.replace(f"Perform = {perform_interval}", f"Perform = {response.headers['refresh_time_interval']}")
                # fin.close()
                # fout = open("/etc/sysmo-agent/sysmo-agent.conf", 'wt')
                # fout.write(data)
                # fout.close()

            # print(response.status_code)
            # print(response.headers['refresh_time_interval'])
            # q.put(response.headers['refresh_time_interval'])

        except KeyboardInterrupt:
            break

        # logging.info(response['refresh_time_interval'])


if __name__ == '__main__':
    LOG_PATH = "/var/log/sysmo-agent/agent.log"
    DEBUG = False
    logger = logging.getLogger(__name__)
    # logging.basicConfig(level=logging.INFO)#, format='%(asctime)s %(levelname)s %(threadName)s : %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    # logger = logging.getLogger()
    # logger.setLevel(logging.INFO)
    JOURNALD_HANDLER = JournalHandler()# SYSLOG_IDENTIFIER='sysmo-agent')
    JOURNALD_HANDLER.setFormatter(logging.Formatter('%(levelname)s : %(message)s'))
    logger.addHandler(JOURNALD_HANDLER)
    logger.setLevel(logging.INFO)
    # Logging Settings
    # logging.basicConfig(
    #     level=logging.INFO if DEBUG is False else logging.DEBUG,
    #     filename='sysmo-agent.log',
    #     format=
    #     '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
    #     datefmt='%Y-%m-%d %H:%M:%S')
    main()
