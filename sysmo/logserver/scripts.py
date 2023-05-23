import plotly.graph_objs as go
import subprocess
import re
from django.utils import timezone
from django.template import loader
from django.conf import settings
from django.core.mail import EmailMessage, send_mail

from django.http import FileResponse
# from .views import log_report_generate_pdf
from .models import MyGroup, Profile, Authenticated_Machine, LogsEden, LogsSurviver, LogsTenured
from datetime import datetime, timedelta, date, time, timezone
from django.utils.timezone import make_aware
import logging
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
import os
from sysmo.settings import DEFAULT_OFFLINE_TIME

# from .views import log_report_generate_pdf


# 檢查主機是否處於Offline狀態 (搭配 crontab 進行定期檢查)
def check_offline():
    logging.info("(check_offline) Enter function.")
    ams = Authenticated_Machine.objects.only('id').order_by("-mygroup")

    for am in ams:
        log = LogsEden.objects.filter(authenticated_machine=am).only(
            "event", "datetime").first()
        today_midnight = make_aware(datetime.combine(date.today(), time.min))
        now = make_aware(datetime.now())
        if not log:
            logging.info("(check_offline) not log.")
            LogsEden.objects.create(
                authenticated_machine=am,
                datetime=now,
                event=None,
            )
        # elif log.datetime < today_midnight:
        #     LogsEden.objects.create(
        #         authenticated_machine=am,
        #         datetime=today_midnight,x
        #         event=None,
        #     )

        if log and am.last_log_update:
            logging.info(
                f"DEFAULT_OFFLINE_TIME = {DEFAULT_OFFLINE_TIME}")
            if now > am.last_log_update + timedelta(
                    seconds=int(am.refresh_time_interval) *
                    DEFAULT_OFFLINE_TIME):  # 2 改成 DEFAULT_OFFLINE_TIME
                td = now.astimezone() - am.last_log_update
                hours, remainder = divmod(td.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                td_str = "OFFLINE for " + str(td.days) + " days " + str(hours) \
                    + " hrs " + str(minutes) + " mins"
                logging.info("td_str : %s" % td_str)

                evs = log.get_event()
                if evs:
                    for event in evs:
                        if event.get("eventtype") == "OFFLINE":
                            log.event = {'eventtype': 'OFFLINE', 'msg': td_str}
                            # logging.info("save")
                            log.save()
                        if now > am.first_warning_time + timedelta(days=7):
                            #logging.info("resend offline warning")
                            if am.bypass_email:
                                logging.info("send_warning_mail_false")
                            else:
                                logging.info("send_warning_mail_true")
                                send_warning_mail({'OFFLINE': td_str},
                                                  ["OFFLINE"], am, now, None)
                                # omc(am.hostName, am.mygroup.name, ["OFFLINE"],
                                #     {'OFFLINE': td_str}, None)
                else:
                    logging.info("(check_offline) not events.")
                    LogsEden.objects.create(authenticated_machine_id=am.id,
                                            event={
                                                'eventtype': 'OFFLINE',
                                                'msg': td_str
                                            },
                                            datetime=now)
                    am.first_warning_time = now
                    am.save()
                    # logging.info("create")
                    if am.bypass_email:
                        logging.info("send_warning_mail_false")
                    else:
                        logging.info("send_warning_mail_true")
                        send_warning_mail({"OFFLINE": td_str}, ["OFFLINE"], am,
                                          now, None)
                        # omc(am.hostName, am.mygroup.name, ["OFFLINE"],
                        #     {'OFFLINE': td_str}, None)

            # If machine is offline
            # if am.last_log_update:
            # if (log and
            #     log.datetime and (
            #         am.last_log_update + timedelta(seconds=int(am.refresh_time_interval)*2)
            #             > make_aware(datetime.now()))):
            #     logging.info("check_offline: log.datetime : %s" % log.datetime)

            #     td = datetime.now().astimezone() - am.last_log_update

            #     hours, remainder = divmod(td.seconds, 3600)
            #     minutes, seconds = divmod(remainder, 60)

            #     td_str = "OFFLINE for " + str(hours) \
            #         + " hrs " + str(minutes) + " mins"

            #     logging.info("td_str : %s" % td_str)

            #     evs = log.get_event()

            #     found = False
            #     if evs:
            #         for e in reversed(evs):
            #             t = e['eventtype']
            #             if t == 'OFFLINE':
            #                 e['msg'] = td_str
            #                 log.event = evs
            #                 found = True
            #         if found is False:
            #             evs.append({'eventtype': 'OFFLINE', 'msg': td_str})
            #             log.event = evs
            #     else:
            #         log.event = {'eventtype': 'OFFLINE', 'msg': td_str}

            #     log.save()
            # logging.info("(check_offline) Added offline message.")
        # logging.info("(check_offline) Exit function.")
    return


# a="path"
# if os.path.exists(a):
#     print('is here')
# else:
#     print('search ')


# 3小時前的Log移入LogsSurvivor
# @profile
def logsEden2Survivor():
    # logging.info("(logsEden2Survivor) Enter function.")
    three_hours_ago = make_aware(datetime.now() - timedelta(hours=24))
    # three_hours_ago = make_aware(datetime.now() - timedelta(days=int(date)))

    ams = Authenticated_Machine.objects.all()
    # logging.info(ams)

    for am in ams:

        logs = LogsEden.objects.defer(
            "cpuUsage", "diskUsage", "memJson", "swapMemJson", "netJson",
            "procByCpu", "procByMem", "event").filter(
                authenticated_machine=am,
                datetime__lt=three_hours_ago)  # .order_by('-datetime')[:1000]
        # logging.info(logs)

        cnt = 0
        for log in logs.iterator():
            LogsSurviver.objects.create(
                authenticated_machine=log.authenticated_machine,
                cpuUsage=log.cpuUsage,
                diskUsage=log.diskUsage,
                memJson=log.memJson,
                swapMemJson=log.swapMemJson,
                netJson=log.netJson,
                procByCpu=log.procByCpu,
                procByMem=log.procByMem,
                event=log.event,
                datetime=log.datetime,
            )
            cnt += 1
            log.delete()
            # logging.info("logsEden2Suvivor moved %d logs" % (cnt))
        # logs.delete()

    # logging.info("(logsEden2Survivor) Exit function.")
    return


# @profile


# removed
def logsSurviver2Tenured():
    # logging.info("(logsSurviver2Tenured) Enter function.")

    datetimeLo = datetime.now() - timedelta(days=32)
    # datetimeLo = datetime.now() - timedelta(days=i) + timedelta(hours=j)

    logs = LogsSurviver.objects.defer("cpuUsage", "diskUsage", "memJson",
                                      "swapMemJson", "netJson", "procByCpu",
                                      "procByMem", "event").filter(
                                          datetime__lte=datetimeLo, ).order_by(
                                              'authenticated_machine',
                                              'datetime')

    tmpDateTime = None
    tmpAm = None
    events = []

    for log in logs.iterator():
        # logging.info("log.event : %s" % (log.event))
        # if event exsists, append to list
        if log.event:
            if tmpAm == log.authenticated_machine and \
               tmpDateTime.date == log.datetime.date and \
               tmpDateTime.hour == log.datetime.hour:
                pass
            else:
                if events:
                    if tmpDateTime and tmpAm:
                        LogsTenured.objects.create(
                            authenticated_machine=tmpAm,
                            event=events,
                            datetime=tmpDateTime,
                            monthly_performance=tmpPerform,
                        )

                    tmpAm = log.authenticated_machine
                    tmpDateTime = log.datetime.replace(
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    events = []
            for ev in log.event:
                #ev['datetime'] = log.datetime.strftime('%Y-%m-%d %H:%M:%S')
                events.append(ev)
        log.delete()
    # logs.delete()
    # logging.info("(logsSurviver2Tenured) Exit function.")
    return


# 資料搬運工
# @profile
def porter():
    # logging.info("(porter) Enter function.")
    logsEden2Survivor()
    logsSurviver2Tenured_new(32)
    Tenured_log_delete(365)

    return


# @profile
def plot_log_line_chart(df, am):
    logging.info("(plot_log_line_chart) Enter function.")
    logging.info(f"df: {df}")
    layout = dict(title="群組：%s<br>主機名稱：%s<br>Server IP：%s" %
                  (am.mygroup.name, am.hostName, am.serverIP),
                  xaxis=dict(title='DateTime',
                             ticklen=5,
                             zeroline=True,
                             showgrid=False),
                  yaxis=dict(title='Resource %',
                             zeroline=True,
                             showgrid=False,
                             showline=True))

    data = [
        go.Scatter(x=df["datetime"],
                   y=df["cpu_usage"],
                   mode='lines',
                   name='cpu',
                   opacity=0.8,
                   marker_color='DodgerBlue'),
        go.Scatter(x=df["datetime"],
                   y=df["memory_usage"],
                   mode='lines',
                   name='memory',
                   opacity=0.8,
                   marker_color='Tomato'),
        go.Scatter(x=df["datetime"],
                   y=df["swap_usage"],
                   mode='lines',
                   name='swap',
                   opacity=0.8,
                   marker_color='MediumSeaGreen'),
    ]

    fig = dict(data=data, layout=layout)
    # logging.info("(plot_log_line_chart) Exit function.")
    return fig


# 生成日期區間 -------------------------------------------------------------------
# @profile
def get_time_threshold(int_url_interval: int, am):
    # logging.info("(get_time_threshold) Enter function.")

    if (int_url_interval == 1):
        # One day ago
        # title = "%s, %s 日報" % (am, (datetime.now().astimezone() -
        #                             timedelta(days=1)).strftime("%Y-%m-%d"))
        title = "%s, %s 日報" % (am, (
            datetime.now().astimezone()).strftime("%Y-%m-%d"))
        # Midnight to midnight
        # end = datetime.combine(datetime.today() - timedelta(days=1),
        #                        time(23, 59)).astimezone()
        end = datetime.combine(datetime.today(), time(23, 59)).astimezone()
        start = datetime.combine(
            end, datetime.min.time()).astimezone()  # today 00:00
        # logging.info("(get_time_threshold : interval = 1) Exit function.")
        return start, end, title

    elif (int_url_interval == 7):
        title = "%s, %d年 第 %d 週週報" % (
            am, (datetime.now() - timedelta(weeks=1)).astimezone().year,
            (datetime.now() -
             timedelta(weeks=1)).astimezone().isocalendar()[1])
        today = date.today().toordinal()
        last = today - 6  # last_sunday
        # Monday to Sunday
        last_monday = last - (last % 7) + 1  # Last Monday
        last_sunday = last_monday + 7  # Last Sunday

        end = datetime.combine(
            date.fromordinal(last_sunday) - timedelta(days=1),
            time(23, 59)).astimezone()
        start = datetime.combine(date.fromordinal(last_monday),
                                 datetime.min.time()).astimezone()
        # logging.info("(get_time_threshold interval = 7) Exit function.")
        return start, end, title

    elif (int_url_interval == 30):
        title = "%s, %d-%d 月月報" % (
            am, (datetime.now() -
                 timedelta(days=datetime.now().day)).astimezone().year,
            (datetime.now() -
             timedelta(days=datetime.now().day)).astimezone().month)
        today = date.today()
        first = today.replace(day=1, month=today.month + 1)

        end = datetime.combine(
            today.replace(day=1, month=today.month + 1) - timedelta(days=1),
            time(23, 59)).astimezone()  # lastMonthLast
        start = datetime.combine(
            end.replace(day=1),
            datetime.min.time()).astimezone()  # lastMonthFirst
        return start, end, title

    elif (int_url_interval == 365):
        title = "%s, %d 年年報" % (am, (datetime.now().year))
        today = date.today() - timedelta(days=365)
        start = datetime.combine(today.replace(month=1, day=1),
                                 datetime.min.time()).astimezone()

        end = datetime.combine(
            today.replace(month=12, day=31),
            datetime.min.time()).astimezone()  # lastMonthLast

        # logging.info("(get_time_threshold interval = 30) Exit function.")
        return start, end, title


# 生成日期區間 -------------------------------------------------------------------
# @profile
def get_time_threshold_2(int_url_interval: int, am, dt):
    from dateutil.relativedelta import relativedelta

    # logging.info("(get_time_threshold) Enter function.")
    if (int_url_interval == 1):
        dt = make_aware(datetime.strptime(dt, "%Y-%m-%d"))
        title = "%s, %s 日報" % (am, dt.strftime("%Y-%m-%d"))
        # Midnight to midnight
        end = datetime.combine(dt, time(23, 59)).astimezone()
        start = datetime.combine(
            end, datetime.min.time()).astimezone()  # yesterday 0:00
        # logging.info("(get_time_threshold : interval = 1) Exit function.")
        return start, end, title

    elif (int_url_interval == 30):
        dt = make_aware(datetime.strptime(dt, "%Y-%m"))
        title = "%s, %d-%d 月月報" % (am, dt.astimezone().year,
                                   dt.astimezone().month)

        end = datetime.combine(
            dt + relativedelta(months=1) - timedelta(days=1),
            time(23, 59)).astimezone()  # lastMonthLast
        start = datetime.combine(
            end.replace(day=1),
            datetime.min.time()).astimezone()  # lastMonthFirst
        return start, end, title

    elif (int_url_interval == 365):
        dt = make_aware(datetime.strptime(dt, "%Y"))
        title = "%s, %d 年年報" % (am, dt.year)
        start = datetime.combine(dt.replace(month=1, day=1),
                                 datetime.min.time()).astimezone()

        end = datetime.combine(
            dt.replace(month=12, day=31),
            datetime.min.time()).astimezone()  # lastMonthLast

        # logging.info("(get_time_threshold interval = 30) Exit function.")
        return start, end, title


# Common Report ---------------------------------------------------------------
# @profile
def get_logs_all(am, start_datetime: datetime, end_datetime: datetime):
    # logging.info("(get_logs_all) Enter function.")

    logs = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime,
        ).union(
            LogsSurviver.objects.defer(
                'diskUsage', 'procByCpu', 'procByMem').filter(
                    authenticated_machine=am,
                    datetime__gte=start_datetime,
                    datetime__lte=end_datetime), ).order_by('datetime')

    # logging.info("(get_logs_all) Exit function.")
    return logs

# Log 平均值計算
class LogWithAvg:

    def __init__(
        self,
        authenticated_machine,
        avg_cpu_usage,
        avg_memory_usage,
        avg_swap_usage,  # avg_disk_usage,
        max_cpu_usage,
        max_memory_usage,
        max_swap_usage,  # max_disk_usage,
        event,
        log_cnt,
        datetime: datetime,
    ):
        self.authenticated_machine = authenticated_machine
        self.avg_cpu_usage = avg_cpu_usage
        self.avg_memory_usage = avg_memory_usage
        self.avg_swap_usage = avg_swap_usage
        #self.avg_disk_usage = avg_disk_usage
        self.max_cpu_usage = max_cpu_usage
        self.max_memory_usage = max_memory_usage
        self.max_swap_usage = max_swap_usage
        #self.max_disk_usage = max_disk_usage
        self.log_cnt = log_cnt
        self.event = event
        self.datetime = datetime

    # 比較 Datetime
    def __eq__(self, __o: object) -> bool:
        return self.datetime == __o.datetime

    # 取得所有Log的Event並存在List
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

    # 確認連線狀態
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

    # 壓縮後的Event不能重複, 故使用Set
    def get_event_type(self):
        evs = self.get_event()
        err_set = set()
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_set.add(e.get('eventtype'))
            return ' and '.join(err_set)

    # 取得
    def get_event_msg(self):
        evs = self.get_event()
        err_list = []
        if evs is None or evs == '':
            return ''
        else:
            for e in evs:
                err_list.append(e['msg'])
            return '\n'.join(err_list)

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
            # if err_list:
            #     err_dict['DISK'] = err_list
            # print(err_dict)
            return err_list, err_dict


# @profile
def get_logs_by_hour(am, start_datetime: datetime, end_datetime: datetime):
    # logging.info("(get_logs_by_hour) Enter function.")

    # if os.path.exists(settings.REPORT_DIR + start)
    # if (int_url_interval == 1):
    # =======
    # filename = "%s-DailyReport-%s" % (start_datetime.strftime("%Y%m%d")+datetime.timedelta(days=-1), str(am))
    filename = "SYSMO-%s-%s-Performance" % (str(
        am.hostName), (start_datetime - timedelta(days=1)).strftime("%Y%m%d"))
    # filename = "%s-DailyReport-%s" % (
    #     (start_datetime - timedelta(days=1)).strftime("%Y%m%d"), str(am))
    time = "%s-日報" % (start_datetime.strftime("%Y%m%d"))

    if not os.path.exists(settings.REPORT_DIR + filename):
        logging.error('%s not Found !' % filename)
    # else:
    #     print('nonsonog')
    # =======
    # elif (int_url_interval == 7):
    #     filename = "%s-%s-WeeklyReport-%s" % (
    #         start.strftime("%Y%m%d"),
    #         end.strftime("%Y%m%d"),
    #         str(am),
    #     )
    #     time = "%s-%s-週報" % (
    #         start.strftime("%Y%m%d"),
    #         end.strftime("%Y%m%d"),
    #     )
    # elif (int_url_interval == 30):
    #     filename = "%s-%s-MonthlyReport-%s" % (start.strftime("%Y"),
    #                                            start.strftime("%m"), str(am))
    #     time = "%s-%s月月報" % (start.strftime("%Y"), start.strftime("%m"))

    tmp_logs = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime,
        ).exclude(cpuUsage=-1).union(LogsSurviver.objects.defer(
            'diskUsage', 'procByCpu', 'procByMem').filter(
                authenticated_machine=am,
                datetime__gte=start_datetime,
                datetime__lte=end_datetime).exclude(cpuUsage=-1),
                                     all=True).order_by('datetime')

    last_log = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime).exclude(cpuUsage=-1).union(
                LogsSurviver.objects.defer(
                    'diskUsage', 'procByCpu', 'procByMem').filter(
                        authenticated_machine=am,
                        datetime__gte=start_datetime,
                        datetime__lte=end_datetime).exclude(cpuUsage=-1),
                all=True).order_by('datetime').last()

    tmp_time = None
    max_cpu: float = 0
    max_memory: float = 0
    max_swap: float = 0

    sum_cpu: float = 0
    sum_memory: float = 0
    sum_swap: float = 0

    cnt = 0

    msg_stack = []
    out_logs = []

    for log in tmp_logs.iterator():
        cnt += 1

        if (log.cpuUsage is None or log.swapUsage() == -1
                or log.memUsage() is None or log.memUsage() == -1
                or log.swapUsage() is None or log.swapUsage() == -1):
            continue

        max_cpu = round(max(log.cpuUsage, max_cpu), 1)
        max_memory = round(max(log.memUsage(), max_memory), 1)
        max_swap = round(max(log.swapUsage(), max_swap), 1)

        sum_cpu += log.cpuUsage
        sum_memory += log.memUsage()
        sum_swap += log.swapUsage()

        if log.event:
            for ev in log.get_event():
                msg_stack.append(ev)

        if (tmp_time is None):
            tmp_time = log.datetime.replace(minute=0, second=0, microsecond=0)
        elif (log.datetime.date() == tmp_time.date()
              and log.datetime.hour == tmp_time.hour
              and log.datetime != last_log.datetime):
            pass
        else:
            tmp_hour_log = LogWithAvg(
                authenticated_machine=log.authenticated_machine,
                max_cpu_usage=max_cpu,
                max_memory_usage=max_memory,
                max_swap_usage=max_swap,
                avg_cpu_usage=round(sum_cpu / cnt, 1),
                avg_memory_usage=round(sum_memory / cnt, 1),
                avg_swap_usage=round(sum_swap / cnt, 1),
                event=msg_stack,
                log_cnt=cnt,
                datetime=tmp_time.astimezone(
                    timezone(timedelta(hours=8), "Asia/Taipei")),
            )

            out_logs.append(tmp_hour_log)

            max_cpu = 0
            max_memory = 0
            max_swap = 0

            sum_cpu = 0
            sum_memory = 0
            sum_swap = 0

            msg_stack = []
            cnt = 0
            tmp_time = log.datetime.replace(minute=0, second=0, microsecond=0)
    # logging.info("(get_logs_by_hour) Exit function.")
    return out_logs


# @profile


def get_logs_by_date(am, start_datetime: datetime, end_datetime: datetime):
    logging.info("(get_logs_by_date) Enter function.")
    logging.info(f"start time : {start_datetime}")
    logging.info(f"end time : {end_datetime}")

    tmp_logs = LogsEden.objects.defer('diskUsage', 'procByCpu',
                                      'procByMem').filter(
                                          authenticated_machine=am,
                                          datetime__gte=start_datetime,
                                          datetime__lte=end_datetime,
                                      ).union(LogsSurviver.objects.defer(
                                          'diskUsage', 'procByCpu',
                                          'procByMem').filter(
                                              authenticated_machine=am,
                                              datetime__gte=start_datetime,
                                              datetime__lte=end_datetime),
                                              all=True).order_by('datetime')

    last_log = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime).exclude(cpuUsage=-1).union(
                LogsSurviver.objects.defer(
                    'diskUsage', 'procByCpu', 'procByMem').filter(
                        authenticated_machine=am,
                        datetime__gte=start_datetime,
                        datetime__lte=end_datetime).exclude(cpuUsage=-1),
                all=True).order_by('datetime').last()

    logging.info('filter done time : {}'.format(datetime.now()))

    tmp_time = None
    max_cpu: float = 0
    max_memory: float = 0
    max_swap: float = 0

    sum_cpu: float = 0
    sum_memory: float = 0
    sum_swap: float = 0

    cnt = 0

    msg_stack = []
    out_logs = []

    for log in tmp_logs.iterator():

        if (log.cpuUsage is None or log.cpuUsage == -1
                or log.memUsage() is None or log.memUsage() == -1
                or log.swapUsage() is None or log.swapUsage() == -1):
            continue

        cnt += 1

        max_cpu = round(max(log.cpuUsage, max_cpu), 1)
        max_memory = round(max(log.memUsage(), max_memory), 1)
        max_swap = round(max(log.swapUsage(), max_swap), 1)

        sum_cpu += log.cpuUsage
        sum_memory += log.memUsage()
        sum_swap += log.swapUsage()

        if log.event:
            for ev in log.get_event():
                msg_stack.append(ev)

        if (tmp_time is None):
            tmp_time = log.datetime.astimezone().replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)

        elif (log.datetime.astimezone().date() == tmp_time.astimezone().date()
              and log.datetime.astimezone().day == tmp_time.astimezone().day
              and log.datetime != last_log.datetime):
            pass
        else:
            tmp_hour_log = LogWithAvg(
                authenticated_machine=log.authenticated_machine,
                max_cpu_usage=max_cpu,
                max_memory_usage=max_memory,
                max_swap_usage=max_swap,
                avg_cpu_usage=round(sum_cpu / cnt, 1),
                avg_memory_usage=round(sum_memory / cnt, 1),
                avg_swap_usage=round(sum_swap / cnt, 1),
                event=msg_stack,
                log_cnt=cnt,
                datetime=tmp_time.astimezone(),
            )
            out_logs.append(tmp_hour_log)

            max_cpu = 0
            max_memory = 0
            max_swap = 0

            sum_cpu = 0
            sum_memory = 0
            sum_swap = 0

            msg_stack = []
            cnt = 0
            tmp_time = log.datetime.astimezone().replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)

    # logging.info("(get_logs_by_date) Exit function.")
    return out_logs


def get_logs_by_month(am, start_datetime: datetime, end_datetime: datetime):
    # logging.info("(get_logs_by_date) Enter function.")
    # logging.info('test start time : {}'.format(datetime.now()))
    logging.info('start time : {}'.format(start_datetime))
    logging.info('end time: {}'.format(end_datetime))

    # get log of not in tenured(hourly data)
    tmp_logs = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime,
        ).union(LogsSurviver.objects.defer('diskUsage', 'procByCpu',
                                           'procByMem').filter(
                                               authenticated_machine=am,
                                               datetime__gte=start_datetime,
                                               datetime__lte=end_datetime),
                all=True).order_by(
                    'datetime')  #.union(LogsTenured.objects.defer)

    tenured_log = LogsTenured.objects.defer('event').filter(
        authenticated_machine=am,
        datetime__gte=start_datetime,
        datetime__lte=end_datetime,
    ).order_by('datetime')

    tenured_last_log = LogsTenured.objects.defer('event').filter(
        authenticated_machine=am,
        datetime__gte=start_datetime,
        datetime__lte=end_datetime,
    ).order_by('datetime').last()

    tenured_out_log = []
    tenured_msg_stack = []
    tenured_tmp_time = None
    tenured_max_cpu: float = 0
    tenured_max_memory: float = 0
    tenured_max_swap: float = 0

    tenured_sum_cpu: float = 0
    tenured_sum_memory: float = 0
    tenured_sum_swap: float = 0

    tenured_cnt = 0
    for log in tenured_log.iterator():
        # print("datetime : %s , avg_cpu_usage : %s" % (log.datetime, log.monthly_performance['avg_cpu_usage']))
        tenured_cnt += 1

        tenured_max_cpu = round(
            max(log.monthly_performance['max_cpu_usage'], tenured_max_cpu), 1)
        tenured_max_memory = round(
            max(log.monthly_performance['max_mem_usage'], tenured_max_memory),
            1)
        tenured_max_swap = round(
            max(log.monthly_performance['max_swap_usage'], tenured_max_swap),
            1)

        tenured_sum_cpu += log.monthly_performance['avg_cpu_usage']
        tenured_sum_memory += log.monthly_performance['avg_mem_usage']
        tenured_sum_swap += log.monthly_performance['avg_swap_usage']

        # if log.event:
        #     for ev in log.get_event():
        #         msg_stack.append(ev)

        if (tenured_tmp_time is None):
            tenured_tmp_time = log.datetime.astimezone().replace(day=1,
                                                                 hour=0,
                                                                 minute=0,
                                                                 second=0,
                                                                 microsecond=0)

        elif (log.datetime.astimezone().date().month
              == tenured_tmp_time.astimezone().date().month
              #   and log.datetime.astimezone().day == tmp_time.astimezone().day
              and log.datetime != tenured_last_log.datetime):
            # print("elif")
            # print(log.datetime.astimezone())
            # print(tmp_time.astimezone())
            pass
        else:
            # print("else")
            # print(log.datetime.astimezone())
            # print(tmp_time.astimezone())
            tenured_tmp_hour_log = LogWithAvg(
                authenticated_machine=log.authenticated_machine,
                max_cpu_usage=round(tenured_max_cpu, 1),
                max_memory_usage=round(tenured_max_memory, 1),
                max_swap_usage=round(tenured_max_swap, 1),
                avg_cpu_usage=round(tenured_sum_cpu / tenured_cnt, 1),
                avg_memory_usage=round(tenured_sum_memory / tenured_cnt, 1),
                avg_swap_usage=round(tenured_sum_swap / tenured_cnt, 1),
                event=tenured_msg_stack,
                log_cnt=tenured_cnt,
                datetime=tenured_tmp_time.astimezone(),
            )
            tenured_out_log.append(tenured_tmp_hour_log)

            tenured_max_cpu = 0
            tenured_max_memory = 0
            tenured_max_swap = 0

            tenured_sum_cpu = 0
            tenured_sum_memory = 0
            tenured_sum_swap = 0

            tenured_msg_stack = []
            tenured_cnt = 0
            tenured_tmp_time = log.datetime.astimezone().replace(day=1,
                                                                 hour=0,
                                                                 minute=0,
                                                                 second=0,
                                                                 microsecond=0)

    # logging.info(tmp_logs)

    last_log = LogsEden.objects.defer(
        'diskUsage', 'procByCpu', 'procByMem').filter(
            authenticated_machine=am,
            datetime__gte=start_datetime,
            datetime__lte=end_datetime).exclude(cpuUsage=-1).union(
                LogsSurviver.objects.defer(
                    'diskUsage', 'procByCpu', 'procByMem').filter(
                        authenticated_machine=am,
                        datetime__gte=start_datetime,
                        datetime__lte=end_datetime).exclude(cpuUsage=-1),
                all=True).order_by('datetime').last()
    # logging.info('filter done time : {}'.format(datetime.now()))
    tmp_time = None
    max_cpu: float = 0
    max_memory: float = 0
    max_swap: float = 0

    sum_cpu: float = 0
    sum_memory: float = 0
    sum_swap: float = 0

    cnt = 0

    msg_stack = []
    out_logs = []

    for log in tmp_logs.iterator():

        # logging.info('interval time : {}'.format(datetime.now()))

        if (log.cpuUsage is None or log.cpuUsage == -1
                or log.memUsage() is None or log.memUsage() == -1
                or log.swapUsage() is None or log.swapUsage() == -1):
            continue

        cnt += 1

        max_cpu = max(log.cpuUsage, max_cpu)
        max_memory = max(log.memUsage(), max_memory)
        max_swap = max(log.swapUsage(), max_swap)

        sum_cpu += log.cpuUsage
        sum_memory += log.memUsage()
        sum_swap += log.swapUsage()

        if log.event:
            for ev in log.get_event():
                msg_stack.append(ev)

        if (tmp_time is None):
            tmp_time = log.datetime.astimezone().replace(day=1,
                                                         hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)

        elif (log.datetime.astimezone().date().month
              == tmp_time.astimezone().date().month
              #   and log.datetime.astimezone().day == tmp_time.astimezone().day
              and log.datetime != last_log.datetime):
            # print("elif")
            # print(log.datetime.astimezone())
            # print(tmp_time.astimezone())
            pass
        else:
            # print("else")
            # print(log.datetime.astimezone())
            # print(tmp_time.astimezone())
            tmp_hour_log = LogWithAvg(
                authenticated_machine=log.authenticated_machine,
                max_cpu_usage=round(max_cpu, 1),
                max_memory_usage=round(max_memory, 1),
                max_swap_usage=round(max_swap, 1),
                avg_cpu_usage=round(sum_cpu / cnt, 1),
                avg_memory_usage=round(sum_memory / cnt, 1),
                avg_swap_usage=round(sum_swap / cnt, 1),
                event=msg_stack,
                log_cnt=cnt,
                datetime=tmp_time.astimezone(),
            )
            out_logs.append(tmp_hour_log)

            max_cpu = 0
            max_memory = 0
            max_swap = 0

            sum_cpu = 0
            sum_memory = 0
            sum_swap = 0

            msg_stack = []
            cnt = 0
            tmp_time = log.datetime.astimezone().replace(day=1,
                                                         hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)
            # print(tmp_time)
    # print(len(out_logs))
    # print(len(tenured_out_log))
    # print(type(out_logs))
    # print(type(tenured_out_log))
    # print(set(out_logs))
    # print(set(tenured_out_log))
    # print(set(out_logs).intersection(set(tenured_out_log)))
    # print(set(out_logs).union(set(tenured_out_log)))
    f_log = []
    # for log in out_logs:
    #     f_log.add(log.datetime)
    #     # for t_log in tenured_out_log:
    #     #     if t_log in

    # print(f_log)
    # print(out_logs.index(datetime))
    # for i in f_log:
    #     print(out_logs)

    # if set(f_log) - set(tenured_out_log):
    # for log in out_logs:
    #     print("log : %s" % log.datetime)
    # for log in tenured_out_log:
    #     print("tlog : %s" % log.datetime)

    if len(out_logs) > len(tenured_out_log):
        for log in out_logs:
            for t_log in tenured_out_log:
                if log == t_log:
                    #                 log.max_cpu_usage = max(log.max_cpu_usage, t_log.max_cpu_usage)
                    #                 log.max_memory_usage= max(log.max_memory_usage, t_log.max_memory_usage)
                    #                 log.max_swap_usage= max(log.max_swap_usage, t_log.max_swap_usage)
                    #                 log.avg_cpu_usage=round((log.avg_cpu_usage + t_log.avg_cpu_usage) / 2, 1),
                    #                 log.avg_memory_usage=round((log.avg_memory_usage + t_log.avg_memory_usage) / 2, 1),
                    #                 log.avg_swap_usage=round((log.avg_swap_usage + t_log.avg_swap_usage) / 2, 1),
                    #                 f_log.append(log)
                    print("%s == %s" % (log.datetime, t_log.datetime))
                else:
                    #                 f_log.append(log)
                    print("%s != %s" % (log.datetime, t_log.datetime))
    else:
        for t_log in tenured_out_log:
            if t_log in out_logs:
                for log in out_logs:
                    if t_log.datetime == log.datetime and t_log not in f_log:
                        t_log.max_cpu_usage = round(
                            max(t_log.max_cpu_usage, log.max_cpu_usage), 1)
                        t_log.max_memory_usage = round(
                            max(t_log.max_memory_usage, log.max_memory_usage),
                            1)
                        t_log.max_swap_usage = round(
                            max(t_log.max_swap_usage, log.max_swap_usage), 1)
                        t_log.avg_cpu_usage = round(
                            (t_log.avg_cpu_usage + log.avg_cpu_usage) / 2, 1)
                        t_log.avg_memory_usage = round(
                            (t_log.avg_memory_usage + log.avg_memory_usage) /
                            2, 1)
                        t_log.avg_swap_usage = round(
                            (t_log.avg_swap_usage + log.avg_swap_usage) / 2, 1)
                        f_log.append(t_log)
                        print("test : %s == %s" %
                              (t_log.datetime, log.datetime))
            else:
                f_log.append(t_log)
                print("test_tlog : %s != %s" % (t_log.datetime, log.datetime))

        for log in out_logs:
            if log in tenured_out_log:
                for log in out_logs:
                    if t_log.datetime == log.datetime and log not in f_log:
                        log.max_cpu_usage = round(
                            max(t_log.max_cpu_usage, log.max_cpu_usage), 1)
                        log.max_memory_usage = round(
                            max(t_log.max_memory_usage, log.max_memory_usage),
                            1)
                        log.max_swap_usage = round(
                            max(t_log.max_swap_usage, log.max_swap_usage), 1)
                        log.avg_cpu_usage = round(
                            (t_log.avg_cpu_usage + log.avg_cpu_usage) / 2, 1)
                        log.avg_memory_usage = round(
                            (t_log.avg_memory_usage + log.avg_memory_usage) /
                            2, 1)
                        log.avg_swap_usage = round(
                            (t_log.avg_swap_usage + log.avg_swap_usage) / 2, 1)
                        f_log.append(log)
                        print("print : %s == %s" %
                              (log.datetime, t_log.datetime))
            else:
                f_log.append(log)
                print("print_log : %s != %s" % (log.datetime, t_log.datetime))

            # for t_log in tenured_out_log:
            # if log.datetime == t_log.datetime:
    #                 max_cpu = max(log.cpuUsage, t_log.cpuUsage)
    #                 max_memory = max(log.memUsage(), t_log.memUsage())
    #                 max_swap = max(log.swapUsage(), t_log.swapUsage())
    #                 sum_cpu = (log.cpuUsage + t_log.cpuUsage) / 2
    #                 sum_memory = (log.memUsage() + t_log.memUsage()) / 2
    #                 sum_swap = (log.swapUsage() + t_log.swapUsage()) / 2
    # else:
    #     for i in range(len(tenured_out_log)):
    #         print("123")

    for log in out_logs:
        print("out_log : %s %s %s" %
              (log.datetime, log.authenticated_machine, log.max_cpu_usage))

    for t_log in tenured_out_log:
        print(
            "tenured_out_log : %s %s %s" %
            (t_log.datetime, t_log.authenticated_machine, t_log.max_cpu_usage))

    # tmp_item = set()
    for log in f_log:
        print("final log : %s %s %s" %
              (log.datetime, log.authenticated_machine, log.max_cpu_usage))
        # tmp_item.add(log.datetime)

    # f_item = []
    # for item in tmp_item:
    #     print(item)
    #     for log in f_log:
    #         if log.datetime != item:
    #             f_item.append(log)

    # for f in f_item:
    #     print("final item : %s %s %s" % (f.datetime, f.authenticated_machine, f.max_cpu_usage))
    # print(log.max_cpu_usage)
    # logging.info("(get_logs_by_date) Exit function.")
    return f_log


# @profile
def send_warning_mail(message, eventtype, am, datetime, last_events):
    logging.info("(send_warning_mail) Enter function.")

    new_eventtype = []
    new_event_msg = []
    for event in eventtype:
        # logging.info("event : %s" % event)
        if last_events == None or event not in last_events:
            logging.info("event : %s" % event)
            logging.info("message.get(event) %s" % message.get(event))
            new_eventtype.append(event)
            new_event_msg.append(message.get(event))
    logging.info("Create Err Log[fixed_eventtype] : %s" % (new_eventtype))

    err_set = set()
    for e in new_eventtype:
        if 'DISK' in e:
            err_set.add(e.rstrip('_*'))
        else:
            err_set.add(e)
    result = ' and '.join(err_set)
    logging.info("err_set : %s" % err_set)
    # logging.info(" new_event_msg : %s" % new_event_msg)
    # logging.info(" result : %s" % result)

    # bypass anything
    if am.bypass_email:
        # logging.info("-> Bypassed authenticated_machine email <-")
        return

    logging.info("-> Send warning email <-")
    if result:
        amgroup = am.mygroup
        groups = MyGroup.objects.filter(name=amgroup)
        mail = groups[0].get_mail()
        for event in new_event_msg:
            html_msg = loader.render_to_string(
                'email.html', {
                    'message': '{}'.format(event),
                    'am': am,
                    'datetime': datetime,
                    'username': "all"
                })
            if result != "OFFLINE":
                result = "%s: HIGH_%s_USAGE - %s" % (
                    result.split('_')[1], result.split('_')[0], event)
            else:
                result = "SYSMO_AGENT_OFFLINE_CRITICAL"
            # close in lab
            if settings.MAIL_SWITCH:
                send_mail(
                    subject="[OS] %s - %s" % (am.hostName, result),
                    message="text version of HTML message",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=mail,
                    fail_silently=True,
                    html_message=html_msg,
                )
        # logging.info("am.first_warning_time update : %s" % datetime)
        am.first_warning_time = datetime
        am.save()

        # logging.info("(send_warning_mail) Exit function.")
    return


# 2022/03/21 computational capacity byte unit
def check_the_policy_fmt(values):
    # logging.info(values)
    re_pattern = r'\d+\.?\d*'

    units = ["K", "M", "G", "T", "P", "E", "Z", "Y"]
    count = -1

    for unit in units:
        count += 1
        if unit in str(values):
            capacity = [
                float(capacity) for capacity in re.findall(re_pattern, values)
            ]
            # logging.info("capacity : %s" % capacity)
            # logging.info(capacity[0] * 1024 ** count)
            return capacity[0] * 1024**count

    return values


# 2023/01/11 fubon new requirement
def check_policy_new(usage, policy: dict, mode, device, diskJson=None):
    # swap default policy : 60~70, 70~80, 80~90, >90
    if device == "SWAP":
        sort_policy = dict(
            sorted(policy.items(), key=lambda item: item[1], reverse=True))
        event = {}
        prePolicy = None
        # skip the whitelist
        if sort_policy.get('Pass') == 1 or sort_policy.get('Pass') == '1':
            return event
        # automatically sort by comparison
        for policyItems in sort_policy:
            if "Pass" in policyItems: return event
            valuePolicy = sort_policy[policyItems]
            if usage >= valuePolicy:
                if prePolicy:
                    if prePolicy == 101 or prePolicy == '101':
                        prePolicy = 100
                    msg = '{device}>={newPolicy} && {device}<{prePolicy}, value={usage}'.format(
                        device=device,
                        newPolicy=valuePolicy,
                        prePolicy=prePolicy,
                        usage=usage)
                    event["eventtype"] = "{}_{}".format(
                        device, policyItems.upper())
                    event["msg"] = msg
                    return event
                else:
                    msg = '{device}>={value}, value={usage}'.format(
                        device=device, value=valuePolicy, usage=usage)
                    event["eventtype"] = "{}_{}".format(
                        device, policyItems.upper())
                    event["msg"] = msg
                    return event
            prePolicy = valuePolicy
        '''
        # Citical
        if (usage >= 90):
            msg = '{device}>={critical}, value={usage}'.format(device=device,
                                                               critical=90,
                                                               usage=usage)
            event["eventtype"] = "{}_CRITICAL".format(device)
            event["msg"] = msg
            return event
        # Major
        elif (usage >= 80):
            msg = '{device}>={major80} && {device}<{critical}, value={usage}'.format(
                device=device, major80=80, critical=90, usage=usage)
            event["eventtype"] = "{}_MAJOR80".format(device)
            event["msg"] = msg
            return event
        # Major
        elif (usage >= 70):
            msg = '{device}>={major70} && {device}<{major80}, value={usage}'.format(
                device=device, major70=70, major80=80, usage=usage)
            event["eventtype"] = "{}_MAJOR70".format(device)
            event["msg"] = msg
            return event
        # Warning
        elif (usage >= 60):
            msg = '{device}>={warning} && {device}<{major70}, value={usage}'.format(
                device=device, warning=60, major70=70, usage=usage)
            event["eventtype"] = "{}_WARNING".format(device)
            event["msg"] = msg
            return event
        '''
    # disk
    elif device == "DISK":
        event_list = []
        for mountpoint, disk_used in usage.items():
            event = {}
            if policy[mountpoint].get('Pass') == 1 or policy[mountpoint].get(
                    'Pass') == '1':
                return event_list
            sort_policy = dict(
                sorted(policy[mountpoint].items(),
                       key=lambda item: item[1],
                       reverse=True))
            prePolicy = None
            # automatically sort by comparison
            for policyItems in sort_policy:
                if "Pass" in policyItems: continue
                valuePolicy: int = int(sort_policy[policyItems])
                if disk_used >= valuePolicy:
                    if prePolicy:
                        if prePolicy == 101 or prePolicy == '101':
                            prePolicy = 100
                        msg = '{device}>={newPolicy} && {device}<{prePolicy}, mountpoint={mountpoint}, value={usage}'.format(
                            device=device,
                            newPolicy=valuePolicy,
                            prePolicy=prePolicy,
                            mountpoint=mountpoint,
                            usage=disk_used)
                        event["eventtype"] = "{}_{}".format(
                            device, policyItems.upper())
                        event["msg"] = msg
                        event_list.append(event)
                    else:
                        msg = '{device}>={value}, mountpoint={mountpoint}, value={usage}'.format(
                            device=device,
                            value=valuePolicy,
                            mountpoint=mountpoint,
                            usage=disk_used)
                        event["eventtype"] = "{}_{}".format(
                            device, policyItems.upper())
                        event["msg"] = msg
                        event_list.append(event)
                    break
                prePolicy = valuePolicy
            '''
            if disk_used >= 99:
                msg = 'DISK>={critical99}, mountpoint={mountpoint}, value={usage}'.format(
                    critical99=99, mountpoint=mountpoint, usage=disk_used)
                event["eventtype"] = "DISK_CRITICAL99"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 98:
                msg = 'DISK>={critical98}, mountpoint={mountpoint}, value={usage}'.format(
                    critical98=98, mountpoint=mountpoint, usage=disk_used)
                event["eventtype"] = "DISK_CRITICAL98"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 97:
                msg = 'DISK>={critical97}, mountpoint={mountpoint}, value={usage}'.format(
                    critical97=97, mountpoint=mountpoint, usage=disk_used)
                event["eventtype"] = "DISK_CRITICAL97"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 95:
                msg = 'DISK>={major95} && DISK<{critical97}, mountpoint={mountpoint}, value={usage}'.format(
                    major95=95,
                    critical97=97,
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_MAJOR95"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 90:
                msg = 'DISK>={major90} && DISK<{major95}, mountpoint={mountpoint}, value={usage}'.format(
                    major90=90,
                    major95=95,
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_MAJOR90"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 80:
                msg = 'DISK>={warning80} && DISK<{major90}, mountpoint={mountpoint}, value={usage}'.format(
                    warning80=80,
                    major90=90,
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_WARNING80"
                event["msg"] = msg
                event_list.append(event)
            elif disk_used >= 70:
                msg = 'DISK>={warning70} && DISK<{warning80}, mountpoint={mountpoint}, value={usage}'.format(
                    warning70=70,
                    warning80=80,
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_WARNING70"
                event["msg"] = msg
                event_list.append(event)
            '''
        return event_list
    # CPU & MEM
    else:
        sort_policy = dict(
            sorted(policy.items(), key=lambda item: item[1], reverse=True))
        event = {}
        prePolicy = None
        if sort_policy.get('Pass') == 1 or sort_policy.get('Pass') == '1':
            return event
        for policyItems in sort_policy:
            if "Pass" in policyItems: return event
            valuePolicy = sort_policy[policyItems]
            if usage >= valuePolicy:
                if prePolicy:
                    if prePolicy == 101 or prePolicy == '101':
                        prePolicy = 100
                    msg = '{device}>={newPolicy} && {device}<={prePolicy}, value={usage}'.format(
                        device=device,
                        newPolicy=valuePolicy,
                        prePolicy=prePolicy,
                        usage=usage)
                    event["eventtype"] = "{}_{}".format(
                        device, policyItems.upper())
                    event["msg"] = msg
                    return event
                else:
                    msg = '{device}>={value}, value={usage}'.format(
                        device=device, value=valuePolicy, usage=usage)
                    event["eventtype"] = "{}_{}".format(
                        device, policyItems.upper())
                    event["msg"] = msg
                    return event
            prePolicy = valuePolicy
        '''
        if (usage >= 95):
            msg = '{device}>={critical}, value={usage}'.format(device=device,
                                                               critical=95,
                                                               usage=usage)
            event["eventtype"] = "{}_CRITICAL".format(device)
            event["msg"] = msg
            return event
        elif (usage >= 90):
            msg = '{device}>={major} && {device}<{critical}, value={usage}'.format(
                device=device, major=90, critical=95, usage=usage)
            event["eventtype"] = "{}_MAJOR".format(device)
            event["msg"] = msg
            return event
        elif (usage >= 80):
            msg = '{device}>={warning} && {device}<{major}, value={usage}'.format(
                device=device, warning=80, major=90, usage=usage)
            event["eventtype"] = "{}_WARNING".format(device)
            event["msg"] = msg
            return event
        '''


def check_policy(usage, policy: dict, mode, device, diskJson=None):
    # logging.info("(check_policy) Enter function.")
    # logging.info("1policy : %s" % type(policy))
    # logging.info("1policy : %s" % (policy))

    if mode == 1:
        event = {}
        if policy.get('Pass') == 1 or policy.get('Pass') == '1':
            return event
        if (usage >= policy.get("Critical")):
            msg = '{device}>={critical}, value={usage}'.format(
                device=device, critical=policy.get("Critical"), usage=usage)
            event["eventtype"] = "{}_CRITICAL".format(device)
            event["msg"] = msg
            # if policy.get('Pass') == 1:
            #     event["Pass"] = 1
            # logging.info("(check_policy : CPU, MEM, SWAP) Exit function.")
            return event

        elif (usage >= policy.get("Major")):
            critical_value = policy.get('Critical')
            if policy.get('Critical') == 101 or policy.get(
                    'Critical') == '101':
                critical_value = 100
            msg = '{device}>={major} && {device}<{critical}, value={usage}'.format(
                device=device,
                major=policy.get("Major"),
                critical=critical_value,
                usage=usage)
            event["eventtype"] = "{}_MAJOR".format(device)
            event["msg"] = msg
            # if policy.get('Pass') == 1:
            #     event["Pass"] = 1
            # logging.info("(check_policy : CPU, MEM, SWAP) Exit function.")
            return event

        elif (usage >= policy.get("Warning")):
            msg = '{device}>={warning} && {device}<{major}, value={usage}'.format(
                device=device,
                warning=policy.get("Warning"),
                major=policy.get("Major"),
                usage=usage)

            event["eventtype"] = "{}_WARNING".format(device)
            event["msg"] = msg
            # if policy.get('Pass') == 1:
            #     event["Pass"] = 1
            # logging.info("(check_policy : CPU, MEM, SWAP) Exit function.")
            return event

    elif mode == 0:
        event_list = []
        cut = -1
        # logging.info("policy : %s" % policy.replace("\'","\""))
        # logging.info(type(policy))
        for mountpoint, disk_used in usage.items():
            compare_lv = {}
            # 2022/03/21 deal with different unit and transforms to "precent" for comparing
            for any_disk_dict in diskJson:
                cut += 1
                if mountpoint in any_disk_dict.values():
                    for policy_level in ['Critical', 'Major', 'Warning']:
                        # logging.info(mountpoint)
                        # logging.info(policy[mountpoint])
                        # logging.info(json.loads(policy.replace("\'","\"")))
                        fmt_capa = check_the_policy_fmt(
                            policy[mountpoint].get(policy_level))
                        # for p in json.loads(policy):
                        #     print(p)
                        # fmt_capa = check_the_policy_fmt(p for p in policy)
                        # fmt_capa = check_the_policy_fmt(p.get(policy_level) for p in policy)
                        if isinstance(fmt_capa, float):
                            disk_total = check_the_policy_fmt(
                                any_disk_dict['total'])
                            level_precent = round(fmt_capa / disk_total * 100,
                                                  2)
                        else:
                            level_precent = float(fmt_capa)
                        # the unit of the result is precent(%)
                        compare_lv[policy_level] = level_precent

            # logging.info("compare_lv : %s" % compare_lv)
            event = {}
            if policy[mountpoint].get('Pass') == 1 or policy[mountpoint].get(
                    'Pass') == '1':
                return event_list
            if disk_used >= compare_lv["Critical"]:
                msg = 'DISK>={critical}, mountpoint={mountpoint}, value={usage}'.format(
                    critical=int(compare_lv["Critical"]),
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_CRITICAL"
                event["msg"] = msg
                # if policy.get('Pass') == 1:
                #     event["Pass"] = 1
                event_list.append(event)

            elif disk_used >= compare_lv["Major"]:
                msg = 'DISK>={major} && DISK<{critical}, mountpoint={mountpoint}, value={usage}'.format(
                    major=int(compare_lv["Major"]),
                    critical=int(compare_lv["Critical"]),
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_MAJOR"
                event["msg"] = msg
                # if policy.get('Pass') == 1:
                #     event["Pass"] = 1
                event_list.append(event)

            elif disk_used >= compare_lv["Warning"]:
                msg = 'DISK>={warning} && DISK<{major}, mountpoint={mountpoint}, value={usage}'.format(
                    warning=int(compare_lv["Warning"]),
                    major=int(compare_lv["Major"]),
                    mountpoint=mountpoint,
                    usage=disk_used)
                event["eventtype"] = "DISK_WARNING"
                event["msg"] = msg
                # if policy.get('Pass') == 1:
                #     event["Pass"] = 1
                event_list.append(event)

        return event_list


# 新增 Log File ----------------------------------------------------------------
# Create warning message if needed
# @profile
def create_err_msg(newLog, am):
    ## if machine_Pass enabled, stoping create any event log
    if am.bypass_email == 1:
        return

    # logging.info("(create_err_msg) Enter function.")
    # logging.info("type am : %s" % type(am))
    event_list = []
    disk_event = None
    # logging.info("newLog : %s" % newLog.get_event())

    cpu_usage = newLog.cpuUsage
    memory_usage = newLog.memUsage()
    swap_usage = newLog.swapUsage()
    disk_usage = newLog.diskUsage
    try:
        cpu_event = check_policy_new(cpu_usage, eval(str(am.cpu_policy)), 1,
                                     "CPU")
        memory_event = check_policy_new(memory_usage,
                                        eval(str(am.memory_policy)), 1, "MEM")
        swap_event = check_policy_new(swap_usage, eval(str(am.swap_policy)), 1,
                                      "SWAP")
    except:
        cpu_event = check_policy_new(cpu_usage, am.cpu_policy, 1, "CPU")
        # {'eventtype': 'MEM_MAJOR', 'msg': 'MEM>=1 && MEM<100, value=10', 'Pass': 1}
        memory_event = check_policy_new(memory_usage, am.memory_policy, 1,
                                        "MEM")
        swap_event = check_policy_new(swap_usage, am.swap_policy, 1, "SWAP")
    if type(am.disk_policy) == str:
        disk_event = check_policy_new(disk_usage, eval(str(am.disk_policy)), 0,
                                      "DISK", am.diskJson)
    else:
        disk_event = check_policy_new(disk_usage, am.disk_policy, 0, "DISK",
                                      am.diskJson)
    # logging.info(am.hostName)
    try:
        last_event, last_event_msg = LogsEden.objects.only('event').filter(
            authenticated_machine_id=am.id,
            datetime__lt=newLog.datetime).first().get_all_event()
    except Exception as e:
        last_event = None
        last_event_msg = None
    # logging.info("(create_err_log : last_event : %s)" % last_event)
    # logging.info("(create_err_log : last_event_msg : %s)" % last_event_msg)

    if cpu_event:
        event_list.append(cpu_event)
    if memory_event:
        event_list.append(memory_event)
    if swap_event:
        event_list.append(swap_event)
    # print(disk_event)
    if disk_event:
        # logging.error(disk_event)
        event_list.extend(disk_event)
    # print(event_list)
    newLog.event = event_list
    newLog.save()

    # if event include pass, the event will bypass from email. So I remove it after I saved that log.
    for e in event_list:
        try:
            if e["Pass"] == 1:
                event_list.remove(e)
        except:
            continue
    # if event exsists,
    # send warning email and snooze 15 mins
    # logging.info("(create_err_log : newLog.get_event() : %s)" % newLog.get_event())
    if (newLog.get_event()):
        # logging.info("value: first %s, last %s" % (newLog.authenticated_machine.first_warning_time, make_aware(datetime.strptime(am.last_log_update, "%Y-%m-%d %H:%M:%S"))))
        # logging.info("value: first %s, last %s" % (newLog.authenticated_machine.first_warning_time, make_aware(datetime.strptime(am.last_log_update, '%Y-%m-%d %H:%M:%S'))))
        # logging.info("type: first %s, last %s" % (type(newLog.authenticated_machine.first_warning_time), type(datetime.strptime(am.last_log_update, '%Y-%m-%d %H:%M:%S'))))
        if (not newLog.authenticated_machine.first_warning_time
                or newLog.authenticated_machine.first_warning_time +
                timedelta(days=7) < make_aware(
                    datetime.strptime(
                        am.last_log_update.strftime('%Y-%m-%d %H:%M:%S'),
                        '%Y-%m-%d %H:%M:%S'))):
            last_event = None
            # logging.info("Out of 60 min!")
            new_event, new_event_msg = newLog.get_all_event()
            logging.info("(create_err_log > send_warning_mail)")
            send_warning_mail(
                new_event_msg,
                new_event,
                am,
                datetime=make_aware(
                    datetime.strptime(
                        newLog.authenticated_machine.last_log_update.strftime(
                            '%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')),
                last_events=last_event)
            # send omc
            # for event in new_event_msg:
            # omc(am.hostName, am.mygroup.name, new_event, new_event_msg,
            #     last_event)
            # omc(am.hostName, am.mygroup, newLog.get_event_type(), newLog.get_event_msg())
        else:
            # logging.info("Checking new_event with last_event")
            #    last_event = None
            new_event, new_event_msg = newLog.get_all_event()
            #logging.info("new_event , new_event_msg : %s , %s" % new_event, new_event_msg)
            logging.info("(create_err_log > send_warning_mail)")
            send_warning_mail(
                new_event_msg,
                new_event,
                am,
                datetime=make_aware(
                    datetime.strptime(
                        newLog.authenticated_machine.last_log_update.strftime(
                            '%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')),
                last_events=last_event)
            # send omc
            # for event in new_event_msg:
            # omc(am.hostName, am.mygroup.name, new_event, new_event_msg,
            #     last_event)
    # logging.info("(create_err_msg) Exit function.")
    return


# @profile
def pdf_report_generator_by_am(am: Authenticated_Machine,
                               int_url_interval: int):
    logging.info("(pdf_report_generator_by_am) Enter function.")
    start, end, title = get_time_threshold(int_url_interval, am)
    # image = settings.STATIC_DIR + '/image/Fubon.svg'
    logging.info(f"start: {start}")
    logging.info(f"end: {end}")

    # 日報表
    if (int_url_interval == 1):
        logs = get_logs_by_hour(am, start, end)
        for log in logs:
            log.datetime = log.datetime.strftime(
                "%Y-%m-%d %H:00:00"
            )  #timezone.localtime(log.datetime).strftime("%Y-%m-%d %H:00:00")
            logging.info(log.datetime)
    # 週/月報表 改成一天一筆資料
    elif (int_url_interval == 7 or int_url_interval == 30):
        logs = get_logs_by_date(am, start, end)
        for log in logs:
            log.datetime = log.datetime.astimezone().strftime(
                "%Y-%m-%d 00:00:00")
            logging.info(log.datetime)
            # log.datetime = timezone.localtime(log.datetime).strftime("%Y-%m-%d")

    elif (int_url_interval == 365):
        logs = get_logs_by_month(am, start, end)
        for log in logs:
            log.datetime = log.datetime.strftime("%Y-%m-%d")

    # Create filename for pdf
    if (int_url_interval == 1):
        filename = "SYSMO-%s-%s-Performance" % (str(am.hostName),
                                                (start).strftime("%Y%m%d"))
        time = "%s-日報" % (start.strftime("%Y%m%d"))

    elif (int_url_interval == 7):
        filename = "SYSMO-%s-%s-%s-Performance" % (str(
            am.hostName), start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        time = "%s-%s-週報" % (
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
        )
        logging.info(f"filename: {filename}, time: {time}")
    elif (int_url_interval == 30):
        filename = "SYSMO-%s-%s-Performance" % (str(
            am.hostName), start.strftime("%Y-%m"))
        time = "%s-%s月月報" % (start.strftime("%Y"), start.strftime("%m"))

    elif (int_url_interval == 365):
        filename = "SYSMO-%s-%s-Performance" % (str(
            am.hostName), start.strftime("%Y"))
        # filename = "%s-yearlyReport-%s" % (start.strftime("%Y"), str(am))
        time = "%s年年報" % (start.strftime("%Y"))

    # elif (int_url_interval == 365):
    #     filename = "SYSMO-%s-%s-Performance" % (str(
    #         am.hostName), start.strftime("%Y"))
    #     time = "%s年年報" % (start.strftime("%Y"))

    env = Environment(loader=FileSystemLoader(settings.TEMPLATE_DIR))
    template = env.get_template("pdf_report.html")
    tmpl_var = {
        'am': am,
        'cpu_policy': eval(str(am.cpu_policy)),
        'swap_policy': eval(str(am.swap_policy)),
        'mem_policy': eval(str(am.memory_policy)),
        'logs': logs,
        'title': time,
        'host': str(am),
    }
    html_out = template.render(tmpl_var)
    HTML(string=html_out, encoding="utf-8").write_pdf(
        "%s/%s" % (settings.REPORT_DIR, filename + ".pdf"),
        stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf_check_report.css')])

    return


# 年報
# @profile
# removed
def pdf_report_generator_by_group(group: MyGroup, int_url_interval: int = 30):

    # logging.info("(pdf_report_generator_by_group) Enter function.")
    start, end, title = get_time_threshold(
        int_url_interval, group.authenticated_machine_set.first())

    # 月報表 改成一天一筆資料
    logs = []
    for am in group.authenticated_machine_set.all():
        tmp_logs = list(get_logs_by_date(am, start, end))
        logs += tmp_logs  # Concat list to logs

    for log in logs:
        log.datetime = timezone.localtime(log.datetime).strftime("%Y-%m-%d")

    filename = "%s-月報-%s" % (start.strftime("%Y-%m"), str(group))

    env = Environment(loader=FileSystemLoader(settings.TEMPLATE_DIR))

    # logging.info("(pdfreport_generator) Loading html template: "
    #              + "pdf_report_monthly.html")
    template = env.get_template("pdf_report_monthly.html")
    tmpl_var = {'mygroup': group, 'logs': logs, 'title': filename}
    html_out = template.render(tmpl_var)

    HTML(string=html_out).write_pdf(
        "%s/%s" % (settings.REPORT_DIR, filename + ".pdf"),
        stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf.css')])
    group = MyGroup.objects.filter(name=am.mygroup)
    # send_report(filename, group, 1)
    return


# Get yesterday's daily report
# @profile
def pdf_daily_check_report(group: str, **custom_date):
    # logging.info("(pdf_daily_check_report) Enter function.")
    if custom_date:
        mydate = make_aware(datetime.strptime(custom_date['time'], "%Y-%m-%d"))
    else:
        mydate = make_aware(datetime.now() - timedelta(days=1))

    # A1, A2
    class a2_event:

        def __init__(self, am, datetime, eventtype, msg):
            self.am = am
            self.datetime = datetime.strftime("%Y-%m-%d, %H:%M:%S")
            self.eventtype = eventtype
            self.msg = msg

    a1_critical = 0
    a1_major = 0
    a1_warning = 0
    a2_events = []

    # B1 to B12
    class b_event:

        def __init__(self, am, datetime, eventtype, msg):
            self.am = am
            self.datetime = datetime.strftime("%Y-%m-%d, %H:%M:%S")
            self.eventtype = eventtype
            self.msg = msg

    b1_events = []
    b2_events = []
    b3_events = []
    b4_events = []
    b5_events = []
    b6_events = []
    b7_events = []
    b8_events = []
    b9_events = []
    b10_events = []
    b11_events = []
    b12_events = []
    offline_events = []

    # C
    # class c2_event:

    #     def __init__(self, am, availibility):
    #         self.am = am
    #         self.availibility = availibility * 100

    # pattern_text = \
    #     r'OFFLINE for (?P<offline_day>\d+) days (?P<offline_hour>\d+) hrs (?P<offline_min>\d+) mins'

    # if mydate < make_aware(datetime.combine(date.today(), time.min)):
    #     c1_all_avail_hour = \
    #         Authenticated_Machine.objects.filter(
    #             mygroup__name=group).count() * 24
    #     c2_avail_hour = 24
    # else:
    #     pass
    #     now = datetime.now().timestamp()
    #     midnight = datetime.now().replace(hour=0,
    #                                       minute=0,
    #                                       second=0,
    #                                       microsecond=0).timestamp()
    #     c2_avail_hour = ((now - midnight) / 60 / 60)
    #     c1_all_avail_hour = c2_avail_hour \
    #         * Authenticated_Machine.objects.filter(mygroup__name=group).count()

    # c1_availibility = None

    # c1_offline_hour = 0
    # c1_offline_min = 0

    # c2_offline_hour = 0
    # c2_offline_min = 0
    # c2_event_list = []

    ams = Authenticated_Machine.objects.filter(mygroup__name=group)

    for am in ams:
        offline_event = None
        logs = LogsEden.objects.defer(
            'cpuUsage', 'diskUsage', 'memJson', 'swapMemJson', 'netJson',
            'procByCpu', 'procByMem').filter(
                authenticated_machine=am,
                datetime__gte=mydate,
                datetime__lt=mydate + timedelta(days=1),
            ).union(
                LogsSurviver.objects.defer(
                    'cpuUsage', 'diskUsage', 'memJson', 'swapMemJson',
                    'netJson', 'procByCpu', 'procByMem').filter(
                        authenticated_machine=am,
                        datetime__gte=mydate,
                        datetime__lt=mydate + timedelta(days=1),
                    ), )
        lastlog = []

        for log in logs.iterator():
            # logging.info("lastlog : %s" % lastlog)
            err_list, err_dict, lastlog = log.merge_event_type(lastlog)
            print("err_list : {}".format(err_list))
            print("err_dict : {}".format(err_dict))
            print("lastlog : {}".format(lastlog))

            if err_list:
                for event in log.get_event():
                    lastlog.append(event.get("eventtype"))
                for ev in err_list:
                    # A1 ~ A2
                    # logging.info("log.get_event() : {}".format(ev))
                    if "CRITICAL" in ev:
                        a1_critical += 1
                        a2_events.append(
                            a2_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "WARNING" in ev:
                        a1_warning += 1

                    elif "MAJOR" in ev:
                        a1_major += 1

                    # B1 ~ B8
                    if "CPU_CRITICAL" in ev:
                        b1_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "CPU_MAJOR" in ev:
                        b2_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "CPU_WARNING" in ev:
                        b3_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_CRITICAL" in ev:
                        b4_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_MAJOR" in ev:
                        b5_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_WARNING" in ev:
                        b6_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_CRITICAL" in ev:
                        b7_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_MAJOR" in ev:
                        b8_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_WARNING" in ev:
                        b9_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_CRITICAL" in ev:
                        b10_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_MAJOR" in ev:
                        b11_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_WARNING" in ev:
                        b12_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))

                    # C
                    if "OFFLINE" in ev:
                        if offline_event and offline_event.datetime == log.datetime.astimezone(
                        ).strftime("%Y-%m-%d, %H:%M:%S"):
                            pass
                        else:
                            offline_event = b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            )
                            offline_events.append(offline_event)

                            a1_critical += 1

                        # match = re.search(pattern_text, err_dict.get(ev))
                        # c1_offline_hour += int(match.group(1))
                        # c1_offline_min += int(match.group(2))
                        # c2_offline_hour += int(match.group(1))
                        # c2_offline_min += int(match.group(2))

    #     c2_offline_rate = \
    #         (c2_offline_hour * 60 + c2_offline_min) \
    #         / (c2_avail_hour * 60)

    #     c2_availibility = round(1 - c2_offline_rate, 2)
    #     c2_event_list.append(c2_event(am, c2_availibility))
    #     c2_offline_hour, c2_offline_min = 0, 0

    # try:
    #     c1_offline_rate = (c1_offline_hour * 60 + c1_offline_min) \
    #         / (c1_all_avail_hour * 60)
    #     c1_availibility = round(1 - c1_offline_rate, 2) * 100
    # except:
    #     logging.info("no")
    """
    # testing
    html_template = get_template('/opt/sysmo-mike/server/logserver/templates/pdf_check_report.html')
    tmpl_var = {
        'date': mydate.strftime("%Y-%m-%d"),
        'mygroup': group,

        # A
        'a1_critical': a1_critical,
        'a1_major': a1_major,
        'a1_warning': a1_warning,
        'a2_events': a2_events,

        # B
        'b1_events': b1_events,
        'b2_events': b2_events,
        'b3_events': b3_events,
        'b4_events': b4_events,
        'b5_events': b5_events,
        'b6_events': b6_events,
        'b7_events': b7_events,
        'b8_events': b8_events,
        'b9_events': b9_events,
        'b10_events': b10_events,
        'b11_events': b11_events,
        'b12_events': b12_events,
        'offline_events': offline_events,

        # C
        'c1_availibility': c1_availibility,
        'c2_event_list': c2_event_list,
    }
    rendered_html = html_template.render(tmpl_var).encode(encoding="UTF-8")
    pdf_file = HTML(string=rendered_html).write_pdf(
        stylesheets=[CSS(settings.STATIC_DIR +  '/css/pdf.css')])



    http_response = HttpResponse(pdf_file, content_type='application/pdf')
    http_response['Content-Disposition'] = 'filename="generate_html.pdf"'

    return http_response
    # testing end
    """

    env = Environment(
        loader=FileSystemLoader([settings.TEMPLATE_DIR, settings.STATIC_DIR]))
    filename = "銀行Linux每日作業檢核表-%s-%s" % (mydate.strftime("%Y%m%d"), str(group))

    logging.info(
        "(pdf_daily_check_report) Loading html template: pdf_check_report.html"
    )
    template = env.get_template("pdf_check_report.html")
    image = settings.STATIC_DIR + '/image/Fubon.svg'
    tmpl_var = {
        'date': mydate.strftime("%Y-%m-%d"),
        'mygroup': group,

        # A
        'a1_critical': a1_critical,
        'a1_major': a1_major,
        'a1_warning': a1_warning,
        # 'a2_events': a2_events,

        # # B
        # 'b1_events': b1_events,
        # 'b2_events': b2_events,
        # 'b3_events': b3_events,
        # 'b4_events': b4_events,
        # 'b5_events': b5_events,
        # 'b6_events': b6_events,
        # 'b7_events': b7_events,
        # 'b8_events': b8_events,
        # 'b9_events': b9_events,
        # 'b10_events': b10_events,
        # 'b11_events': b11_events,
        # 'b12_events': b12_events,
        # 'offline_events': offline_events,
        'a2_events': sorted(a2_events, key=lambda s: s.datetime),

        # B
        'b1_events': sorted(b1_events, key=lambda s: s.datetime),
        'b2_events': sorted(b2_events, key=lambda s: s.datetime),
        'b3_events': sorted(b3_events, key=lambda s: s.datetime),
        'b4_events': sorted(b4_events, key=lambda s: s.datetime),
        'b5_events': sorted(b5_events, key=lambda s: s.datetime),
        'b6_events': sorted(b6_events, key=lambda s: s.datetime),
        'b7_events': sorted(b7_events, key=lambda s: s.datetime),
        'b8_events': sorted(b8_events, key=lambda s: s.datetime),
        'b9_events': sorted(b9_events, key=lambda s: s.datetime),
        'b10_events': sorted(b10_events, key=lambda s: s.datetime),
        'b11_events': sorted(b11_events, key=lambda s: s.datetime),
        'b12_events': sorted(b12_events, key=lambda s: s.datetime),
        'offline_events': sorted(offline_events, key=lambda s: s.datetime),

        # C
        # 'c1_availibility': c1_availibility,
        # 'c2_event_list': c2_event_list,
        'image': image
    }
    html_out = template.render(tmpl_var)

    HTML(string=html_out, encoding="utf-8").write_pdf(
        "%s/%s" % (settings.REPORT_DIR, filename + ".pdf"),
        stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf_check_report.css')])
    # Nick chang
    # stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf.css')])
    logging.info("group : {}".format(group))

    # subprocess.run([
    #     "chown", "nginx:nginx",
    #     "%s/%s.pdf" % (settings.REPORT_DIR, filename)
    # ],
    #                check=True,
    #                stdout=subprocess.PIPE,
    #                universal_newlines=True)

    # send_report(filename, group, 0)

    return


# @profile


# 日月週年
def send_report(filename: str, group, mode):
    logging.info("(send_report) Enter! Send %s" % filename)
    email_to = []
    title = ""
    if mode == 1:
        email_to = group[0].get_mail()
        title = ("[值班專用]%s-%s-效能日報表") % (str(
            group[0].name), filename.split('-')[1])
        content = filename
    elif mode == 7:
        email_to = group[0].get_mail()
        title = ("[值班專用]%s-%s-效能週報表") % (str(
            group[0].name), filename.split('-')[1])
        content = filename
    elif mode == 30:
        email_to = group[0].get_mail()
        title = ("[值班專用]%s-%s-效能月報表") % (str(
            group[0].name), filename.split('-')[1])
        content = filename
    elif mode == 365:
        email_to = group[0].get_mail()
        title = ("[值班專用]%s-%s-效能年報表") % (str(
            group[0].name), filename.split('-')[1])
        content = filename
    elif mode == 100:
        pfs = Profile.objects.all()
        for pf in pfs:
            email_to.append(pf.user.email)
        title = "[值班專用]銀行Linux每日作業檢核表"
        content = filename

    if email_to is not None:
        logging.info("(send_report) Email %s" % email_to)
        try:
            mail = EmailMessage(
                title,  # Title
                content,  # 內文
                settings.EMAIL_HOST_USER,
                email_to)
            mail.attach_file("%s/%s.pdf" % (settings.REPORT_DIR, filename))
            mail.send()
            logging.info("(send_report) Report sent!")

        except Exception as e:
            logging.error("(send_report) Email Error:%s" % e)

    return


def diet():
    # tmp_event = {}
    # evt_offline = set()
    # evt_dw = set()
    # evt_dm = set()
    # evt_dc = set()
    # evt_cw = set()
    # evt_cm = set()
    # evt_cc = set()
    # evt_mw = set()
    # evt_mm = set()
    # evt_mc = set()
    # evt_sw = set()
    # evt_sm = set()
    # evt_sc = set()

    # logs = LogsTenured.objects.defer("event","monthly_performance").all()
    # for log in logs.iterator():
    #     try:
    #           for l in log.event:
    #               for i in log.event[l]:
    #                   switch (i) {
    #                   case "DISK_WARNING": evt_dw.add(l)
    #                   case "DISK_MAJOR": evt_dm.add(l)
    #                   case "DISK_CRITICAL": evt_dc.add(l)
    #                   case "CPU_WARNING": evt_cw.add(l)
    #                   case "CPU_MAJOR": evt_cm.add(l)
    #                   case "CPU_CRITICAL": evt_cc.add(l)
    #                   case "MEMORY_WARNING": evt_mw.add(l)
    #                   case "MEMORY_MAJOR": evt_mm.add(l)
    #                   case "MEMORY_CRITICAL": evt_mc.add(l)
    #                   case "SWAP_WARNING": evt_sw.add(l)
    #                   case "SWAP_MAJOR": evt_sm.add(l)
    #                   case "SWAP_CRITICAL": evt_sc.add(l)
    #                   case "OFFLINE": evt_offline.add(l)
    # }
    #
    #     except Exception as e:
    #         print(e)

    cnt = 0
    for log in LogsEden.objects.all():
        try:
            # log.diskUsage = log.diskUsage[]
            log.memJson = log.memJson['usedPercent']
            log.swapMemJson = log.swapMemJson['usedPercent']
            log.netJson = None
            log.save()
            print(cnt)
        except Exception as e:
            print(e)

        cnt += 1

    for log in LogsSurviver.objects.all():
        try:
            log.memJson = log.memJson['usedPercent']
            log.swapMemJson = log.swapMemJson['usedPercent']
            log.netJson = None
            log.save()
            print(cnt)
        except Exception as e:
            print(e)

        cnt += 1

    return


def omc(hostname: str, group: str, eventtype, message, last_event):
    new_event_msg = []
    for event in eventtype:
        # logging.info("event : %s" % event)
        if last_event == None or event not in last_event:
            new_event_dict = {}
            # logging.info("remove : %s" % event)
            if "OFFLINE" in event or "CRITICAL" in event:
                level = 4
            elif "MAJOR" in event:
                level = 3
            elif "WARNING" in event:
                level = 1
            # new_eventtype.append(event)
            new_event_dict['level'] = level
            new_event_dict['event'] = message.get(event)
            new_event_msg.append(new_event_dict)
    # logging.info("Enter OMC")
    # OMC path "/opt/omc/em/script.sh"
    # group = "TEST"
    for msg in new_event_msg:
        cmd = "sh /opt/sendsms/sendsms.sh %s %s %s \"%s\" \"%s\"" % (
            "SYSMO", group, msg['level'], msg['event'], hostname)
        logging.info("OMC cmd: %s" % cmd)
        if settings.MAIL_SWITCH:
            os.system(cmd)


# 2022/03/15 delete the Tenured data once a year
def Tenured_log_delete(log_interval: int):
    time_cycle = datetime.now() - timedelta(days=log_interval)
    logs = LogsTenured.objects.filter(datetime__lte=time_cycle)

    if logs.exists():
        regular_del = logs.delete()
        logging.info("Rugular delete : {}.".format(regular_del[1]))
    else:
        pass


def logsSurviver2Tenured_new(date):
    # Tenured Log:
    # max_perform: {cpu, mem, swap}
    # avg_perform; {cpu, mem, swap}
    # logging.info("(logsSurviver2Tenured) Enter function.")
    datetimeLo = datetime.now() - timedelta(days=date)

    # ams
    ams = Authenticated_Machine.objects.all().only('id')

    for am in ams:
        logs = LogsSurviver.objects.defer(
            'procByCpu', 'procByMem', 'event').filter(
                datetime__lte=datetimeLo,
                authenticated_machine_id=am.id).exclude(cpuUsage=-1)
        last_log = LogsSurviver.objects.defer(
            'procByCpu', 'procByMem', 'event').filter(
                datetime__lte=datetimeLo,
                authenticated_machine_id=am.id).exclude(cpuUsage=-1).first()
        cnt = 0
        max_cpu = max_memory = max_swap = 0
        sum_cpu = sum_memory = sum_swap = 0
        tmpDateTime = None
        event = {}

        for log in logs.iterator():
            # the first log
            if tmpDateTime is None:
                tmpDateTime = log.datetime.replace(minute=0,
                                                   second=0,
                                                   microsecond=0)
            if (log.datetime.date() == tmpDateTime.date()
                    and log.datetime.hour == tmpDateTime.hour
                    and log.datetime != last_log.datetime):

                cnt += 1

                max_cpu = max(log.cpuUsage, max_cpu)
                max_memory = max(log.memJson, max_memory)
                max_swap = max(log.swapMemJson, max_swap)

                sum_cpu += log.cpuUsage
                sum_memory += log.memJson
                sum_swap += log.swapMemJson
                # if bool(log.event):
                #     event[datetime.strftime(log.datetime,
                #                             '%Y-%m-%d %H:%M:%S')] = log.event
            else:
                print('create!!')
                print(am)
                print(tmpDateTime)
                # add the LastLog data
                # if bool(last_log.event):
                #     event[datetime.strftime(
                #         last_log.datetime,
                #         '%Y-%m-%d %H:%M:%S')] = last_log.event
                tmp_hour_log = LogWithAvg(
                    authenticated_machine=last_log.authenticated_machine,
                    max_cpu_usage=max(last_log.cpuUsage, max_cpu),
                    max_memory_usage=max(last_log.memJson, max_memory),
                    max_swap_usage=max(last_log.swapMemJson, max_swap),
                    avg_cpu_usage=round((sum_cpu + last_log.cpuUsage) /
                                        (cnt + 1), 1) if sum_cpu != 0 else 0,
                    avg_memory_usage=round(
                        (sum_memory + last_log.memJson) / (cnt + 1), 1),
                    avg_swap_usage=round(
                        (sum_swap + last_log.swapMemJson) / (cnt + 1), 1),
                    event=event,
                    log_cnt=cnt + 1,
                    datetime=tmpDateTime,
                )
                # create the last data
                LogsTenured.objects.create(
                    authenticated_machine=tmp_hour_log.authenticated_machine,
                    # event=event,
                    datetime=tmp_hour_log.datetime,
                    monthly_performance={
                        'max_cpu_usage': tmp_hour_log.max_cpu_usage,
                        'max_mem_usage': tmp_hour_log.max_memory_usage,
                        'max_swap_usage': tmp_hour_log.max_swap_usage,
                        'avg_cpu_usage': tmp_hour_log.avg_cpu_usage,
                        'avg_mem_usage': tmp_hour_log.avg_memory_usage,
                        'avg_swap_usage': tmp_hour_log.avg_swap_usage
                    },
                )
                tmpDateTime = log.datetime.replace(minute=0,
                                                   second=0,
                                                   microsecond=0)
            log.delete()
        # +++++++++++++++++++++++++++++
        LogsSurviver.objects.defer('procByCpu', 'procByMem', 'event').filter(
            datetime__lte=datetimeLo, authenticated_machine_id=am.id).delete()
        # +++++++++++++++++++++++++++++

    # cnt = 0
    # Change_AM = False
    # tmpDateTime = None
    # events = []
    # max_cpu = max_memory = max_swap = 0
    # sum_cpu = sum_memory = sum_swap = 0

    # for log in logs.iterator():
    #     if (log.cpuUsage is None or log.cpuUsage == -1 or log.memJson is None
    #             or log.memJson == -1 or log.swapMemJson is None
    #             or log.swapMemJson == -1):
    #         continue
    #     else:

    #         # deal with the first log
    #         if (tmpDateTime is None):
    #             tmpDateTime = log.datetime.replace(minute=0,
    #                                                second=0,
    #                                                microsecond=0)
    #         # deal with diff AM
    #         if Change_AM == False:
    #             tmp_hour_log = LogWithAvg(
    #                 authenticated_machine=log.authenticated_machine,
    #                 max_cpu_usage=0,
    #                 max_memory_usage=0,
    #                 max_swap_usage=0,
    #                 avg_cpu_usage=0,
    #                 avg_memory_usage=0,
    #                 avg_swap_usage=0,
    #                 event=0,
    #                 log_cnt=0,
    #                 datetime=tmpDateTime,
    #             )
    #         # check the am changed
    #         Change_AM = (log.authenticated_machine ==
    #                      tmp_hour_log.authenticated_machine)
    #         # last_log can be removed?
    #         if (log.datetime.date() == tmpDateTime.date()
    #                 and log.datetime.hour == tmpDateTime.hour
    #                 and log.datetime != last_log.datetime and Change_AM):

    #             cnt += 1

    #             max_cpu = max(log.cpuUsage, max_cpu)
    #             max_memory = max(log.memJson, max_memory)
    #             max_swap = max(log.swapMemJson, max_swap)

    #             sum_cpu += log.cpuUsage
    #             sum_memory += log.memJson
    #             sum_swap += log.swapMemJson
    #             events.append(log.event)

    #             # move this out of the loop, the sum value is wired
    #             tmp_hour_log = LogWithAvg(
    #                 authenticated_machine=log.authenticated_machine,
    #                 max_cpu_usage=max_cpu,
    #                 max_memory_usage=max_memory,
    #                 max_swap_usage=max_swap,
    #                 avg_cpu_usage=round(sum_cpu / cnt, 1),
    #                 avg_memory_usage=round(sum_memory / cnt, 1),
    #                 avg_swap_usage=round(sum_swap / cnt, 1),
    #                 event=events,
    #                 log_cnt=cnt,
    #                 datetime=tmpDateTime,
    #             )
    #         else:
    #             # tmp_hour_log is in here?
    #             print('create Tenured data')
    #             print('create am : {}'.format(
    #                 tmp_hour_log.authenticated_machine))
    #             print("log datetime2 : {}".format(log.datetime))
    #             print("tmp datetime2 : {}".format(tmpDateTime))

    #             LogsTenured.objects.create(
    #                 authenticated_machine=tmp_hour_log.authenticated_machine,
    #                 event=events,
    #                 datetime=tmp_hour_log.datetime,
    #                 monthly_performance={
    #                     'max_cpu_usage': tmp_hour_log.max_cpu_usage,
    #                     'max_mem_usage': tmp_hour_log.max_memory_usage,
    #                     'max_swap_usage': tmp_hour_log.max_swap_usage,
    #                     'avg_cpu_usage': tmp_hour_log.avg_cpu_usage,
    #                     'avg_mem_usage': tmp_hour_log.avg_memory_usage,
    #                     'avg_swap_usage': tmp_hour_log.avg_swap_usage
    #                 },
    #             )
    #             # reset LogWithAvg Objects data
    #             tmpDateTime = log.datetime.replace(
    #                 minute=0,
    #                 second=0,
    #                 microsecond=0,
    #             )
    #             cnt = 0
    #             max_cpu = max_memory = max_swap = 0
    #             sum_cpu = sum_memory = sum_swap = 0
    #             events = []
    # logs.delete()
    # logging.info("(logsSurviver2Tenured) Exit function.")
    return


def pdf_daily_check_report_all(group: str, **custom_date):
    # logging.info("(pdf_daily_check_report_all) Enter function.")
    if custom_date:
        mydate = make_aware(datetime.strptime(
            custom_date['time'], "%Y-%m-%d")).replace(minute=0,
                                                      second=0,
                                                      microsecond=0)
    else:
        mydate = make_aware(
            datetime.strptime(
                datetime.strftime(datetime.now() - timedelta(days=1),
                                  "%Y-%m-%d"),
                "%Y-%m-%d")).replace(minute=0, second=0, microsecond=0)
        # mydate = make_aware(datetime.now() - timedelta(days=1)).replace(minute=0, second=0, microsecond=0)

    # A1, A2
    class a2_event:

        def __init__(self, am, datetime, eventtype, msg):
            self.am = am
            self.datetime = datetime.strftime("%Y-%m-%d, %H:%M:%S")
            self.eventtype = eventtype
            self.msg = msg

    a1_critical = 0
    a1_major = 0
    a1_warning = 0
    a2_events = []

    # B1 to B12
    class b_event:

        def __init__(self, am, datetime, eventtype, msg):
            self.am = am
            self.datetime = datetime.strftime("%Y-%m-%d, %H:%M:%S")
            self.eventtype = eventtype
            self.msg = msg

    b1_events = []
    b2_events = []
    b3_events = []
    b4_events = []
    b5_events = []
    b6_events = []
    b7_events = []
    b8_events = []
    b9_events = []
    b10_events = []
    b11_events = []
    b12_events = []
    offline_events = []

    # C
    # class c2_event:

    #     def __init__(self, am, availibility):
    #         self.am = am
    #         self.availibility = availibility * 100

    pattern_text = \
        r'OFFLINE for (?P<offline_day>\d+) days (?P<offline_hour>\d+) hrs (?P<offline_min>\d+) mins'

    # if mydate < make_aware(datetime.combine(date.today(), time.min)):
    #     c1_all_avail_hour = \
    #         Authenticated_Machine.objects.all().count() * 24
    #     c2_avail_hour = 24
    # else:
    #     pass
    #     now = datetime.now().timestamp()
    #     midnight = datetime.now().replace(hour=0,
    #                                       minute=0,
    #                                       second=0,
    #                                       microsecond=0).timestamp()
    #     c2_avail_hour = ((now - midnight) / 60 / 60)
    #     c1_all_avail_hour = c2_avail_hour \
    #         * Authenticated_Machine.objects.all().count()

    # c1_availibility = None

    # c1_offline_day = 0
    # c1_offline_hour = 0
    # c1_offline_min = 0

    # c2_offline_day = 0
    # c2_offline_hour = 0
    # c2_offline_min = 0
    # c2_event_list = []
    if group == "All":
        ams = Authenticated_Machine.objects.all()
    else:
        # logging.info("not all")
        group = MyGroup.objects.get(name=group)
        ams = Authenticated_Machine.objects.filter(mygroup__name=group)
        # logging.info(group)

    for am in ams:
        offline_event = None
        # logging.info(mydate)
        logs = LogsEden.objects.filter(
            authenticated_machine=am,
            datetime__gte=mydate,
            datetime__lt=mydate + timedelta(days=1),
        ).union(
            LogsSurviver.objects.filter(
                authenticated_machine=am,
                datetime__gte=mydate,
                datetime__lt=mydate + timedelta(days=1),
            ), )
        lastlog = []

        for log in logs.iterator():
            # logging.info(log.datetime)
            # logging.info("lastlog : %s" % lastlog)
            err_list, err_dict, lastlog = log.merge_event_type(lastlog)

            # lastlog = []

            if err_list:
                for event in log.get_event():
                    lastlog.append(event.get("eventtype"))
                for ev in err_list:
                    # A1 ~ A2
                    # logging.info("log.get_event() : {}".format(ev))
                    if "CRITICAL" in ev:
                        a1_critical += 1
                        a2_events.append(
                            a2_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "WARNING" in ev:
                        a1_warning += 1

                    elif "MAJOR" in ev:
                        a1_major += 1

                    # B1 ~ B8
                    if "CPU_CRITICAL" in ev:
                        b1_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "CPU_MAJOR" in ev:
                        b2_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "CPU_WARNING" in ev:
                        b3_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_CRITICAL" in ev:
                        b4_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_MAJOR" in ev:
                        b5_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "MEM_WARNING" in ev:
                        b6_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_CRITICAL" in ev:
                        b7_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_MAJOR" in ev:
                        b8_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "SWAP_WARNING" in ev:
                        b9_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_CRITICAL" in ev:
                        b10_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_MAJOR" in ev:
                        b11_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))
                    elif "DISK_WARNING" in ev:
                        b12_events.append(
                            b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            ))

                    # C
                    if "OFFLINE" in ev:
                        # offline_events.append(
                        #     b_event(
                        #         log.authenticated_machine.hostName,
                        #         log.datetime.astimezone(),
                        #         ev, # event type
                        #         err_dict.get(ev), # event msg
                        #     ))
                        # a1_critical += 1

                        if offline_event and offline_event.datetime == log.datetime.astimezone(
                        ).strftime("%Y-%m-%d, %H:%M:%S"):
                            pass
                        else:
                            offline_event = b_event(
                                log.authenticated_machine.hostName,
                                log.datetime.astimezone(),
                                ev,
                                err_dict.get(ev),
                            )
                            offline_events.append(offline_event)

                            a1_critical += 1
                            # offline_events.append(
                            #     b_event(
                            #         log.authenticated_machine.hostName,
                            #         log.datetime.astimezone(),
                            #         ev,
                            #         err_dict.get(ev),
                            #     ))

                        # match = re.search(pattern_text, err_dict.get(ev))
                        # logging.info(match, pattern_text)
                        # c1_offline_day += int(match.group(1))
                        # c1_offline_hour += int(match.group(2))
                        # c1_offline_min += int(match.group(3))
                        # c2_offline_day += int(match.group(1))
                        # c2_offline_hour += int(match.group(2))
                        # c2_offline_min += int(match.group(3))

    #     c2_offline_rate = \
    #         (c2_offline_hour * 60 + c2_offline_min) \
    #         / (c2_avail_hour * 60)

    #     c2_availibility = round(1 - c2_offline_rate, 2)
    #     c2_event_list.append(c2_event(am, c2_availibility))
    #     c2_offline_hour, c2_offline_min = 0, 0

    # try:
    #     c1_offline_rate = (c1_offline_hour * 60 + c1_offline_min) \
    #         / (c1_all_avail_hour * 60)
    #     c1_availibility = round(1 - c1_offline_rate, 2) * 100
    # except:
    #     logging.info("no")

    env = Environment(
        loader=FileSystemLoader([settings.TEMPLATE_DIR, settings.STATIC_DIR]))
    if group == "All":
        filename = "銀行Linux每日作業檢核表-%s" % (mydate.strftime("%Y%m%d"))
    else:
        filename = "銀行Linux每日作業檢核表-%s-%s" % (mydate.strftime("%Y%m%d"),
                                             str(group))

    logging.info(
        "(pdf_daily_check_report) Loading html template: pdf_check_report.html"
    )
    template = env.get_template("pdf_check_report.html")
    image = settings.STATIC_DIR + '/image/Fubon.svg'
    tmpl_var = {
        'date':
        mydate.strftime("%Y-%m-%d"),
        'mygroup':
        group,

        # A
        'a1_critical':
        a1_critical,
        'a1_major':
        a1_major,
        'a1_warning':
        a1_warning,
        # 'a2_events': a2_events,

        # # B
        # 'b1_events': b1_events,
        # 'b2_events': b2_events,
        # 'b3_events': b3_events,
        # 'b4_events': b4_events,
        # 'b5_events': b5_events,
        # 'b6_events': b6_events,
        # 'b7_events': b7_events,
        # 'b8_events': b8_events,
        # 'b9_events': b9_events,
        # 'b10_events': b10_events,
        # 'b11_events': b11_events,
        # 'b12_events': b12_events,
        # 'offline_events': offline_events,
        'a2_events':
        sorted(a2_events, key=lambda s: s.datetime),

        # B
        'b1_events':
        sorted(b1_events, key=lambda s: s.datetime),
        'b2_events':
        sorted(b2_events, key=lambda s: s.datetime),
        'b3_events':
        sorted(b3_events, key=lambda s: s.datetime),
        'b4_events':
        sorted(b4_events, key=lambda s: s.datetime),
        'b5_events':
        sorted(b5_events, key=lambda s: s.datetime),
        'b6_events':
        sorted(b6_events, key=lambda s: s.datetime),
        'b7_events':
        sorted(b7_events, key=lambda s: s.datetime),
        'b8_events':
        sorted(b8_events, key=lambda s: s.datetime),
        'b9_events':
        sorted(b9_events, key=lambda s: s.datetime),
        'b10_events':
        sorted(b10_events, key=lambda s: s.datetime),
        'b11_events':
        sorted(b11_events, key=lambda s: s.datetime),
        'b12_events':
        sorted(b12_events, key=lambda s: s.datetime),
        'offline_events':
        sorted(list({item.am: item
                     for item in offline_events}.values()),
               key=lambda s: s.datetime),
        # 'offline_events': offline_events,

        # C
        # 'c1_availibility': c1_availibility,
        # 'c2_event_list': c2_event_list,
        'image':
        image
    }
    html_out = template.render(tmpl_var)

    HTML(string=html_out, encoding="utf-8").write_pdf(
        "%s/%s" % (settings.REPORT_DIR, filename + ".pdf"),
        stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf_check_report.css')])
    # Nick chang
    # stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf.css')])
    logging.info("group : {}".format("ALL"))
    # subprocess.run([
    #     "chown", "nginx:nginx",
    #     "%s/%s.pdf" % (settings.REPORT_DIR, filename)
    # ],
    #                check=True,
    #                stdout=subprocess.PIPE,
    #                universal_newlines=True)

    # send_report(filename, group, 0)

    return
