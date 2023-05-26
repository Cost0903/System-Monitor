from typing import Any
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from sysmo.settings import DEFAULT_INTERVAL, DEFAULT_WARNING, DEFAULT_MAJOR, DEFAULT_CRITICAL
import logging
import pandas as pd


# Set policy default value
def cpumem_default_json():
    logging.info(
        str("{'Pass': %s, 'Warning': %s, 'Major': %s, 'Critical': %s}") %
        (0, DEFAULT_WARNING, DEFAULT_MAJOR, DEFAULT_CRITICAL))
    return str("{'Pass': %s, 'Warning': %s, 'Major': %s, 'Critical': %s}") % (
        0, DEFAULT_WARNING, DEFAULT_MAJOR, DEFAULT_CRITICAL)


# def swap_default_json():
#     return str(
#         "{'Pass': %s, 'Warning': %s, 'Major': %s, 'Major80': %s, 'Critical': %s}"
#     ) % (0, SWAP_WARNING, SWAP_MAJOR70, SWAP_MAJOR80, SWAP_CRITICAL)


# 2022/03/21 modified the capacity format(cancel any "B" char)
def sizeof_fmt(num):
    num = float(num)
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']:
        if abs(num) < 1024.0:
            return "%3.1f%s" % (num, unit)
        num /= 1024.0
    return "%.1f%s" % (num, 'YiB')


class MyGroup(models.Model):
    name = models.CharField(max_length=30, unique=True, primary_key=True)
    description = models.CharField(max_length=100, blank=True)
    mail = models.TextField(blank=True)

    def __str__(self):
        return (self.name)

    class Meta:
        verbose_name = "主機群組"
        verbose_name_plural = "主機群組"

    def get_mail(self):
        return str(self.mail).split(',')


class Profile(models.Model):
    user = models.OneToOneField(User,
                                on_delete=models.PROTECT,
                                verbose_name='使用者')
    mygroup = models.ManyToManyField(MyGroup, verbose_name='訂閱群組清單')

    # @receiver(post_save, sender=User)
    # def create_user_profile(sender, instance, created, **kwargs):
    #     if created:
    #         Profile.objects.create(user=instance)

    # @receiver(post_save, sender=User)
    # def save_user_profile(sender, instance, **kwargs):
    #     instance.profile.save()

    class Meta:
        verbose_name = "訂閱設定"
        verbose_name_plural = "訂閱設定"

    def __str__(self):
        return str(self.user)


# DEFAULT_INTERVAL = LOG_INTERVAL  # 30 secs
# DEFAULT_MAJOR = MAJOR
# DEFAULT_WARNING = WARNING
# DEFAULT_CRITICAL = CRITICAL


# create the object for resetting JSONField of the DiskPolicy
class AMDiskJsonField(models.JSONField):
    pass


# reparse MpountPoint capacity of the DiskJson
class MountPointJsonField(models.JSONField):
    pass


#
# class DiskField(models.JSONField):
#     description = "A Disk Partition's information"

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)


class CommonPolicyJsonField(models.JSONField):
    pass


class Authenticated_Machine(models.Model):
    # Basic Host Info ---------------------------------------------------------
    hostName = models.CharField('主機名稱', max_length=30)
    hostID = models.CharField('主機ID', max_length=40)
    hostOS = models.CharField('作業系統', max_length=30)
    cpuCount = models.IntegerField('CPU數目', null=True, blank=True)
    diskJson = MountPointJsonField('Disk資訊', null=True, blank=True)

    # ISMS Info --------------------------------------------------------------
    asset_ID = models.CharField("資產編號", max_length=20, null=True, blank=True)
    serverIP = models.CharField("IP位址", max_length=30, null=True, blank=True)
    depository_name = models.CharField("保管人",
                                       max_length=20,
                                       null=True,
                                       blank=True)
    backup_name = models.CharField("備援人", max_length=20, null=True, blank=True)

    # Group
    mygroup = models.ForeignKey(MyGroup,
                                blank=True,
                                null=True,
                                on_delete=models.SET_NULL,
                                verbose_name="主機群組")

    # Interval Setting --------------------------------------------------------
    cpu_policy = CommonPolicyJsonField(verbose_name="CPU 告警(%)",
                                       default=cpumem_default_json)
    memory_policy = CommonPolicyJsonField(verbose_name="Memory 告警(%)",
                                          default=cpumem_default_json)
    disk_policy = AMDiskJsonField(verbose_name="Disk 告警(%)",
                                  blank=True,
                                  default=dict)
    swap_policy = CommonPolicyJsonField(verbose_name="Swap 告警(%)",
                                        default=cpumem_default_json)

    refresh_time_interval = models.PositiveIntegerField(
        verbose_name="監控週期(sec)", default=DEFAULT_INTERVAL)
    # 主機報錯靜音 (All)
    bypass_email = models.BooleanField("關閉告警", default=False)
    # -------------------------------------------------------------------------
    hostUptime = models.IntegerField('開機時間', null=True, blank=True)
    created_at = models.DateTimeField('主機註冊時間',
                                      auto_now_add=False,
                                      auto_now=True)
    last_log_update = models.DateTimeField('最新更新時間', null=True, blank=True)
    first_warning_time = models.DateTimeField('最新告警時間', null=True, blank=True)

    def __str__(self):
        return '%s-%s' % (self.mygroup, self.hostName)

    # 主機清單
    class Meta:
        verbose_name = "註冊主機"
        verbose_name_plural = "主機清單"

    def get_disk_table(self):
        df = pd.DataFrame.from_records(self.diskJson).reindex(
            ['device', 'mountpoint', 'free', 'used', 'total', 'usedPercent'],
            axis=1,
        )
        df.index = df.index + 1

        # 2022/04/12 debug
        # if 'B' not in df['free']:
        # df['free'] = df['free'].astype(float).apply(lambda x : "%.1fB" % (x))
        # df['free'] = df['free'].astype(float).apply(lambda x: sizeof_fmt(x))
        # df['used'] = df['used'].astype(float).apply(lambda x: sizeof_fmt(x))
        # df['total'] = df['total'].astype(float).apply(lambda x: sizeof_fmt(x))
        df['usedPercent'] = df['usedPercent'].astype(float).apply(
            lambda x: "%.1f" % (x) + "%")
        return df

    # get mountpoint like ["/", "/var", "/opt", "usr"]
    def get_mountpoint(self):
        mountpoint = []
        for disk in self.diskJson:
            mountpoint.append(disk['mountpoint'])
        return mountpoint

    # disk warning
    def make_warning_disk_data(self):
        import json
        diskArray = []
        for disk in self.diskJson:
            diskDist = {}
            diskDist['mountpoint'] = disk['mountpoint']
            diskDist['warning_percent'] = DEFAULT_WARNING
            diskDist['major_percent'] = DEFAULT_MAJOR
            diskDist['warning'] = "100GiB"
            diskDist['major'] = "10GiB"
            diskArray.append()
        return json.dumps(diskArray)


def EdenMountPoint_():
    return {'mountpoint': -1}


# 僅會保存七天內的資料 (It will be all the logs less than seven days in the future)
class LogsEden(models.Model):
    authenticated_machine = models.ForeignKey(Authenticated_Machine,
                                              null=True,
                                              on_delete=models.CASCADE)

    # Monitoring --------------------------------------------------------------
    cpuUsage = models.FloatField(null=True, blank=True, default=-1)
    diskUsage = models.JSONField(null=True,
                                 blank=True,
                                 default=EdenMountPoint_)
    memJson = models.FloatField(null=True, blank=True)
    swapMemJson = models.FloatField(null=True, blank=True)
    netJson = models.JSONField(null=True, blank=True)
    procByCpu = models.JSONField(null=True, blank=True)
    procByMem = models.JSONField(null=True, blank=True)

    # Other Info --------------------------------------------------------------
    event = models.JSONField(null=True, blank=True, default=None)
    # The server receives the log at this time
    datetime = models.DateTimeField('Log Time', null=True)

    class Meta:
        verbose_name = "最新日誌檔"
        verbose_name_plural = "最新日誌檔"
        ordering = ['-datetime']
        indexes = [
            models.Index(fields=['datetime']),
        ]

    def __str__(self):
        # example : ansible 2021-12-28 00:00:00
        return str(self.authenticated_machine) + " " + str(self.datetime)

    # delete when we change the models
    def memUsage(self):
        if self.memJson is None:
            return -1
        else:
            return float(self.memJson)

    # delete when we change the models
    def swapUsage(self):
        if self.swapMemJson is None:
            return -1
        else:
            return float(self.swapMemJson)

    # dashboard2 process_by_cpu
    def get_proc_cpu_table(self):
        df = pd.DataFrame.from_records(self.procByCpu).reindex(
            ['full_command', 'cpu', 'mem', 'pid', 'command_name'],
            axis=1,
        )
        df.index = df.index + 1
        df['cpu'] = df['cpu'].astype(str).apply(lambda x: x + '%')
        df['mem'] = df['mem'].astype(str).apply(lambda x: x + '%')

        del df['command_name']
        dfStyler = df.style.set_properties(**{'text-align': 'left'})
        dfStyler.set_table_styles(
            [dict(selector='th', props=[('text-align', 'left')])])

        return df

    # dashboard2 process_by_mem
    def get_proc_mem_table(self):
        df = pd.DataFrame.from_records(self.procByMem).reindex(
            ['full_command', 'cpu', 'mem', 'pid', 'command_name'],
            axis=1,
        )
        df.index = df.index + 1
        df['cpu'] = df['cpu'].astype(str).apply(lambda x: x + '%')
        df['mem'] = df['mem'].astype(str).apply(lambda x: x + '%')

        del df['command_name']
        # style here ?
        dfStyler = df.style.set_properties(**{'text-align': 'left'})
        dfStyler.set_table_styles(
            [dict(selector='th', props=[('text-align', 'left')])])

        return df

    # Make event to list type
    def get_event(self):
        evs = self.event

        # if none
        if evs is None or evs == '':
            return None

        # if evs is a dict: only one element
        # convert it to a list
        elif type(evs) == dict:
            to_list = []
            to_list.append(evs)
            return to_list

        # if evs is a list of dict
        else:
            return evs

    def get_offline(self):
        evs = self.get_event()
        if self.cpuUsage < 0:
            return 'Offline'
        elif evs is None or evs == '':
            return 'Online'
        else:
            for e in reversed(evs):
                if e['eventtype'] == 'OFFLINE':
                    return 'Offline'
            return 'Online'

    def get_event_type(self):
        evs = self.get_event()
        err_set = set()
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_set.add(e.get('eventtype'))
            return ' and '.join(err_set)

    def merge_event_type(self, last_event):

        # logging.info("lastlog : %s" % last_event)
        evs = self.get_event()
        err_dict = {}
        err_list = []
        last_log = []
        if evs is None or evs == '':
            logging.info("None - err_list : %s" % err_list)
            logging.info("None - err_dict : %s" % err_dict)
            return err_list, err_dict, last_log
        else:
            # logging.info("append - lastlog")
            for e in evs:
                last_log.append(e.get("eventtype"))
                if e.get("eventtype") not in last_event and e.get(
                        "eventtype") != "OFFLINE":
                    if 'CPU' in e.get('eventtype'):
                        err_list.append(e.get('eventtype'))
                        err_dict[e.get('eventtype')] = e.get('msg')
                        # err_dict['CPU'] = e.get('eventtype')
                    if 'MEM' in e.get('eventtype'):
                        err_list.append(e.get('eventtype'))
                        err_dict[e.get('eventtype')] = e.get('msg')
                        # err_dict['MEM'] = e.get('eventtype')
                    if 'SWAP' in e.get('eventtype'):
                        err_list.append(e.get('eventtype'))
                        err_dict[e.get('eventtype')] = e.get('msg')
                        # err_dict['SWAP'] = e.get('eventtype')
                    if 'DISK' in e.get('eventtype'):
                        # disk_dict = {}
                        mountpoint = e.get('msg').split(
                            "mountpoint=")[-1].split(',')[0]
                        err_dict["%s_%s" % (e.get('eventtype'),
                                            mountpoint)] = e.get('msg')
                        # disk_dict[e.get('eventtype')] = mountpoint
                        err_list.append("%s_%s" %
                                        (e.get('eventtype'), mountpoint))
                elif e.get("eventtype") == "OFFLINE":
                    err_list.append(e.get('eventtype'))
                    err_dict[e.get('eventtype')] = e.get('msg')

            # logging.info("end - err_list : %s" % err_list)
            # logging.info("end - err_dict : %s" % err_dict)
            return err_list, err_dict, last_log

    def get_all_event(self):
        evs = self.get_event()
        err_dict = {}
        err_list = []
        if evs is None or evs == '':
            return err_list, err_dict
        else:
            for e in evs:
                if 'CPU' in e.get('eventtype'):
                    err_list.append(e.get('eventtype'))
                    err_dict[e.get('eventtype')] = e.get('msg')
                    # err_dict['CPU'] = e.get('eventtype')
                if 'MEM' in e.get('eventtype'):
                    err_list.append(e.get('eventtype'))
                    err_dict[e.get('eventtype')] = e.get('msg')
                    # err_dict['MEM'] = e.get('eventtype')
                if 'SWAP' in e.get('eventtype'):
                    err_list.append(e.get('eventtype'))
                    err_dict[e.get('eventtype')] = e.get('msg')
                    # err_dict['SWAP'] = e.get('eventtype')
                if 'DISK' in e.get('eventtype'):
                    # disk_dict = {}
                    mountpoint = e.get('msg').split("mountpoint=")[-1].split(
                        ',')[0]
                    err_dict["%s_%s" %
                             (e.get('eventtype'), mountpoint)] = e.get('msg')
                    # disk_dict[e.get('eventtype')] = mountpoint
                    err_list.append("%s_%s" % (e.get('eventtype'), mountpoint))
                if 'OFFLINE' in e.get("eventtype"):
                    err_list.append(e.get('eventtype'))
                    err_dict[e.get('eventtype')] = e.get('msg')

            # if err_list:
            #     err_dict['DISK'] = err_list
            # print(err_dict)
            return err_list, err_dict

    def get_event_msg(self):
        evs = self.get_event()
        err_list = []
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_list.append(e['msg'])
            return '\n'.join(err_list)


# 7天 ~ 33天的資料 (It will be hour's logs between seven days and thirty-two days in the future)
class LogsSurviver(models.Model):
    authenticated_machine = models.ForeignKey(Authenticated_Machine,
                                              null=True,
                                              on_delete=models.CASCADE)

    # Monitoring --------------------------------------------------------------
    cpuUsage = models.IntegerField(null=True, blank=True)
    diskUsage = models.JSONField(null=True, blank=True)
    memJson = models.JSONField(null=True, blank=True)
    swapMemJson = models.JSONField(null=True, blank=True)
    netJson = models.JSONField(null=True, blank=True)
    procByCpu = models.JSONField(null=True, blank=True)
    procByMem = models.JSONField(null=True, blank=True)

    # Other Info --------------------------------------------------------------
    event = models.JSONField(null=True, blank=True)
    datetime = models.DateTimeField('Log Time', null=True)

    class Meta:
        verbose_name = "年輕日誌檔"
        verbose_name_plural = "年輕日誌檔"
        ordering = ['-datetime']
        indexes = [
            models.Index(fields=['datetime']),
        ]

    def __str__(self):
        return str(self.authenticated_machine) + str(self.datetime)

    def memUsage(self):
        return int(self.memJson['usedPercent'])

    def swapUsage(self):
        return int(self.swapMemJson['usedPercent'])

    def get_event(self):
        evs = self.event

        # if none
        if evs is None or evs == '':
            return None

        # if evs is a dic: only one element
        # convert it to a list
        elif type(evs) == dict:
            to_list = []
            to_list.append(evs)
            return to_list

        # if evs is a list of dict
        else:
            return evs

    def get_offline(self):
        evs = self.get_event()
        if self.cpuUsage < 0:
            return 'Offline'
        elif evs is None or evs == '':
            return 'Online'
        else:
            for e in reversed(evs):
                if e['eventtype'] == 'OFFLINE':
                    return 'Offline'
            return 'Online'

    def get_event_type(self):
        evs = self.get_event()
        err_list = []
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_list.append(e.get('eventtype'))
            return '\n'.join(err_list)

    def get_event_msg(self):
        evs = self.get_event()
        err_list = []
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_list.append(e['msg'])
            return '\n'.join(err_list)


# 33天以上：僅會保存存在錯誤 Event 的資料 (It will be monthly logs between after thirty-two days in the future)
# interval will affect the range of keeping a log
class LogsTenured(models.Model):

    authenticated_machine = models.ForeignKey(Authenticated_Machine,
                                              null=True,
                                              on_delete=models.CASCADE)
    datetime = models.DateTimeField('Log Time', null=True)
    monthly_performance = models.JSONField(null=True, blank=True)
    # Other Info --------------------------------------------------------------
    event = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "終生日誌檔"
        verbose_name_plural = "終生日誌檔"
        ordering = ['-datetime']

    def __str__(self):
        return str(self.authenticated_machine) + " " + str(self.datetime)


class LogsHistory(models.Model):
    hostName = models.CharField(max_length=30)
    hostID = models.CharField(max_length=40)

    cpuUsage = models.IntegerField(null=True, blank=True, default=-1)
    diskUsage = models.JSONField(null=True,
                                 blank=True,
                                 default=EdenMountPoint_)
    memJson = models.JSONField(null=True, blank=True)
    swapMemJson = models.JSONField(null=True, blank=True)
    netJson = models.JSONField(null=True, blank=True)
    procByCpu = models.JSONField(null=True, blank=True)
    procByMem = models.JSONField(null=True, blank=True)

    event = models.JSONField(null=True, blank=True, default=None)
    datetime = models.DateTimeField('Log Time', null=True)

    class Meta:
        verbose_name_plural = "刪除主機歷史紀錄"

    def __str__(self):
        return self.hostName + str(self.datetime)
