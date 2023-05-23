import pandas as pd
import json
import csv
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from django.contrib import messages
from django.shortcuts import render
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from sysmo.settings import DISK_CRITICAL, DISK_MAJOR, DISK_WARNING
from .models import MyGroup, Authenticated_Machine, DEFAULT_WARNING, DEFAULT_MAJOR, DEFAULT_CRITICAL, sizeof_fmt
from .models import LogsEden, LogsSurviver
from .scripts import *
from tzlocal import get_localzone
from datetime import datetime, timedelta, time, timezone
from django.utils.timezone import make_aware
from plotly.offline import plot
# from pprint import pprint
from django.views.decorators.csrf import csrf_exempt
import logging
import zoneinfo

# logging setting
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='[%d/%b/%Y %H:%M:%S]')


# Dashboard 中特定主機的100筆資料---------------------------------------------------------
# Only show the CPU, Memory, Swap AND Waring column
# The Disk Information is in the DiskTable(硬碟資訊)
@login_required
def latestlogbyID(request, url_hostID):
    # logging.info("Enter function (latestbymac)")
    time_threshold = datetime.now().astimezone() - timedelta(hours=6)
    # logging.info(f"time_threshold: {time_threshold}")

    am = Authenticated_Machine.objects.get(hostID=url_hostID)

    # Get logs from LogsEden and LogsSurviver
    logs = LogsEden.objects.defer('procByCpu', 'procByMem', 'event').filter(
        authenticated_machine=am, datetime__gt=time_threshold).union(
            LogsSurviver.objects.defer(
                'procByCpu', 'procByMem',
                'event').filter(authenticated_machine=am,
                                datetime__gt=time_threshold)).order_by(
                                    '-datetime')[:100]  # only show 100 logs
    usageList = []
    if not logs:
        return render(request, "latestlogbyID.html", {'am': am, 'logs': logs})

    for log in logs.iterator():
        # logging.info(f"memUsage: {type(log.memJson)}")
        usageVec = {
            'cpu_usage':
            log.cpuUsage,
            'memory_usage':
            log.memJson,
            # log.memUsage(),
            'swap_usage':
            log.swapMemJson,
            'datetime':
            log.datetime.astimezone(timezone(timedelta(hours=8),
                                             "Asia/Taipei")),
        }
        # logging.debug(
        #     f"log.datetime : {log.datetime.astimezone(timezone(timedelta(hours=8),'Asia/Taipei'))}")
        usageList.append(usageVec)

    df = pd.DataFrame.from_records(usageList)
    # logging.info(f"df info: {df}")

    fig = plot_log_line_chart(df, am)
    plot_div = plot(fig,
                    output_type='div',
                    include_plotlyjs=True,
                    show_link=False)

    return render(request, "latestlogbyID.html", {
        'am': am,
        'logs': logs,
        'plot_div': plot_div
    })


# 儲存的報表----------------------------------------------------------------------
# @login_required
# @profile
# def select_machine(request, nextpage,
#                    url_interval):  # check this, maybe need remove
#     # logging.info("Enter function (select_machine)")

#     if request.method == "GET":
#         ams = Authenticated_Machine.objects.all().order_by("mygroup")

#     if request.method == "POST":
#         search = request.POST.get('search')

#         if search == "" or search == ' ':
#             ams = Authenticated_Machine.objects.all().order_by("mygroup")

#         else:
#             ams = Authenticated_Machine.objects.filter(
#                 hostName__icontains=search).union(
#                     Authenticated_Machine.objects.filter(
#                         hostID__icontains=search),
#                     Authenticated_Machine.objects.filter(
#                         mygroup__name__icontains=search).order_by("mygroup"))

#     if nextpage == "saved-report":
#         interval = int(url_interval)
#         if interval == 1:
#             title = "%s 日報" % ((datetime.now().astimezone() -
#                                 timedelta(days=1)).strftime("%Y-%m-%d"))
#         elif interval == 7:
#             title = "%d年 第 %d 週週報" % (
#                 (datetime.now() - timedelta(weeks=1)).astimezone().year,
#                 (datetime.now() -
#                  timedelta(weeks=1)).astimezone().isocalendar()[1])
#         elif interval == 30:
#             title = "%d-%d 月月報" % (
#                 (datetime.now() -
#                  timedelta(days=datetime.now().day)).astimezone().year,
#                 (datetime.now() -
#                  timedelta(days=datetime.now().day)).astimezone().month)
#         else:
#             title = "ERROR"
#     elif nextpage == "set-query":
#         title = "請選擇要查詢的主機"

#     return render(request, "select_machine.html", {
#         'ams': ams,
#         'interval': url_interval,
#         'title': title,
#         'nextpage': nextpage
#     })


def reports(request, url_interval,
            url_hostID):  # check this, maybe need remove
    logging.info("Enter Function : (get_report)")
    data = str(request.GET.get("filename"))
    logging.info(data)
    am = Authenticated_Machine.objects.get(hostID=url_hostID)
    logging.info("url_interval : %s" % url_interval)
    try:
        file = open(settings.REPORT_DIR + '/' + data, 'rb')
    except:
        logging.info("Enter to except")
        # env = Environment(loader=FileSystemLoader(settings.TEMPLATE_DIR))
        pdf_report_generator_by_am(am, int(url_interval))
        file = open(settings.REPORT_DIR + '/' + data, 'rb')
        # return HttpResponseNotFound("hello")
    # file = open('reports/test.pdf', 'rb')
    response = FileResponse(file)
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment;filename=' + data
    return response


'''
def generate_pdf_report(int_url_interval:int, am):
    start, end, _ = get_time_threshold(int_url_interval, am)

    df = pd.DataFrame.from_records(Log_Warehouse.objects.filter(
        authenticated_machine = am,
        datetime__lt=end,
        datetime__gte=start
        ).order_by('datetime').values())
    df['datetime'] = df['datetime'].dt.strftime("%Y-%m-%d %H時")
    del df["id"]
    del df["authenticated_machine_id"]
    del df["log_cnt"]
    del df["err_msg"]
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]

    mypath = os.getcwd() + "/tmp_report.csv"
    df.to_csv(mypath)

    logging.info('Generate CSV report')

    return
'''


# 儲存的報表 ---------------------------------------------------------------------
@login_required
# @profile
def saved_report(request, url_hostID, url_interval):
    logging.info("Enter function (saved-report)")
    int_url_interval = int(url_interval)
    am = Authenticated_Machine.objects.get(hostID=url_hostID)
    start, end, title = get_time_threshold(int_url_interval, am)
    # logging.info("(saved report) time threshold start:%s, end:%s, am:%s"
    #              % (start, end, am))

    logs = None

    # 日報表
    if (int_url_interval == 1):
        logs = get_logs_by_hour(am, start, end)

    # 週/月報表 改成一天一筆資料
    elif (int_url_interval == 7 or int_url_interval == 30):
        logs = get_logs_by_date(am, start, end)

    # logging.info("(saved-report) %d" % (len(logs)))

    try:
        logs[0]
    except Exception:
        title = "此段時段" + str(am) + "無資料"
        return render(request, "report_by_hour.html", {
            'logs': logs,
            'title': title,
            'am': am
        })

    usageList = []
    if logs is None:
        logging.info("(saved-report) No logs.")
        return render(request, 'report_by_hour.html', {'am': am, 'logs': logs})

    for log in logs:
        usageDict = {
            'cpu_usage': log.avg_cpu_usage,
            'memory_usage': log.avg_memory_usage,
            'swap_usage': log.avg_swap_usage,
            'datetime': log.datetime
        }
        usageList.append(usageDict)
    # print(usageList)

    df = pd.DataFrame.from_records(usageList)
    df['datetime'] = df['datetime'].dt.tz_convert(get_localzone())

    # plot
    fig = plot_log_line_chart(df, am)
    plot_div = plot(fig,
                    output_type='div',
                    include_plotlyjs=True,
                    show_link=False)

    if (int_url_interval == 1):
        filename = "SYSMO-%s-%s-Performance.pdf" % (str(am.hostName),
                                                    (start).strftime("%Y%m%d"))
        return render(
            request, "report_by_hour.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'filename': filename,
                'url_interval': url_interval,
                'url_hostID': url_hostID
            })
    elif (int_url_interval == 7 or int_url_interval == 30):
        if (int_url_interval == 7):
            filename = "SYSMO-%s-%s-%s-Performance.pdf" % (str(
                am.hostName), start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        else:
            filename = "SYSMO-%s-%s-Performance.pdf" % (str(
                am.hostName), start.strftime("%Y%m"))
        return render(
            request, "report_by_date.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'filename': filename,
                'url_interval': url_interval,
                'url_hostID': url_hostID
            })


# def check_filepath():
#     if os.path.isfile()


# 自訂報表 ----------------------------------------------------------------------
@login_required
# @profile
def custom_query_report(request):
    # logging.info("Enter function (custom_query_report)")
    if (request.method == "POST"):

        str_hostID = request.POST.get("hostID")
        str_start_date = request.POST.get("start_date")
        str_end_date = request.POST.get("end_date")
        str_view = request.POST.get("view")

        try:
            am = Authenticated_Machine.objects.get(hostID=str_hostID)
        except Exception:
            error = "輸入錯誤：找不到輸入的 hostID"
            messages.error(request, error)
            return render(request, "set_query.html", {})

        start_date = make_aware(datetime.strptime(str_start_date, "%Y-%m-%d"))
        end_date = make_aware(datetime.strptime(str_end_date, "%Y-%m-%d"))

        # Error Check
        if (start_date > end_date):
            error = "輸入錯誤：結束日期不能先於起始日期"
            messages.error(request, error)
            return render(request, "set_query.html", {'my_hostID': str_hostID})

        if (start_date > make_aware(datetime.now())
                or end_date > make_aware(datetime.now())):
            error = "輸入錯誤：起始日期不能先於現在日期"
            messages.error(request, error)
            return render(request, "set_query.html", {'my_hostID': str_hostID})

        start_datetime = make_aware(datetime.combine(start_date, time(0, 0)))
        end_datetime = make_aware(datetime.combine(end_date, time(23, 59)))

        title = "自訂搜尋：%s~%s" % (str_start_date, str_end_date)

        if str_view == "all":
            logs = get_logs_all(am, start_datetime, end_datetime)
        elif str_view == "hour":
            logs = get_logs_by_hour(am, start_datetime, end_datetime)
        elif str_view == "day":
            logs = get_logs_by_date(am, start_datetime, end_datetime)
        else:
            error = 'Unexpected error!'
            messages.error(request, error)
            return render(request, "set_query.html", {})

        if logs is None:
            title = "時間內找不到日誌檔"
            messages.error(request, title)
            return render(request, 'set_query.html', {})

        usageList = []
        if str_view == "all":
            for log in logs.iterator():
                usageDict = {
                    'cpu_usage': log.cpuUsage,
                    'memory_usage': log.memUsage(),
                    'swap_usage': log.swapUsage(),
                    'datetime': log.datetime
                }
                usageList.append(usageDict)
        elif str_view == "hour" or str_view == "day":
            for log in logs:
                usageDict = {
                    'cpu_usage': log.avg_cpu_usage,
                    'memory_usage': log.avg_memory_usage,
                    'swap_usage': log.avg_swap_usage,
                    'datetime': log.datetime
                }
                usageList.append(usageDict)

        logging.info(usageList)
        df = pd.DataFrame.from_records(usageList)
        df['datetime'] = df['datetime'].dt.tz_convert(get_localzone())

        # plot
        fig = plot_log_line_chart(df, am)
        plot_div = plot(fig,
                        output_type='div',
                        include_plotlyjs=True,
                        show_link=False)
    if str_view == "all":
        return render(
            request, "report_single_log.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 0
            })
    elif str_view == "hour":
        return render(
            request, "report_by_hour.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 0
            })
    elif str_view == "day":
        return render(
            request, "report_by_date.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 0
            })


@login_required
# @profile
def set_query_for_self_defined_report(request, url_hostID, url_interval):
    # logging.info("Enter function (set_quert_for_self_defined_report)")
    if request.method == "GET":
        return render(request, "set_query.html", {'my_hostID': url_hostID})


# 每日點檢表 --------------------------------------------------------------------
@login_required
# @profile
def query_check_report(request):
    # logging.info("Enter function (query_check_report)")
    if (request.method == "GET"):
        mygroups = MyGroup.objects.all()
        return render(request, "query_check_report.html",
                      {'mygroups': mygroups})

    if (request.method == "POST"):
        str_group = request.POST.get("group")
        r_date_str = request.POST.get("date")
        logging.info(r_date_str)
        if str_group == "All":
            group = "All"
            filename = "銀行Linux每日作業檢核表-%s.pdf" % (r_date_str.replace("-", ""))
            # filename = "%s-CheckReport.pdf" % (r_date_str.replace(
            #     "-", ""))
        else:
            group = MyGroup.objects.get(name=str_group)
            filename = "銀行Linux每日作業檢核表-%s-%s.pdf" % (r_date_str.replace(
                "-", ""), str_group)

        # logging.info("query_check_report : filename : !%s!" % (filename))

        mydate = make_aware(datetime.strptime(r_date_str, "%Y-%m-%d"))

        # A1, A2
        class a2_event:

            def __init__(self, am, datetime, eventtype, msg):
                self.am = am
                self.datetime = datetime
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
                self.datetime = datetime
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

        # class offline_event:  # offline object

        #     def __init__(self, am, datetime, state):
        #         self.am = am
        #         self.datetime = datetime
        #         self.state = state

        # def get_duration(offline_events):
        #     start_date = ""
        #     end_date = ""
        #     for offline_event in offline_events:
        #         offline = 1
        #     return ""

        pattern_text = \
            r'OFFLINE for (?P<offline_hour>\d+) hrs (?P<offline_min>\d+) mins'

        if request.POST.get('download'):
            # logging.info(settings.REPORT_DIR + '/' + str(filename))
            # logging.info(filename)
            # logging.info(smart_str(filename))
            # logging.info()
            try:
                file = open(settings.REPORT_DIR + '/' + str(filename),
                            'rb')  # + filename
            except:
                pdf_daily_check_report_all(str_group, time=r_date_str)
                file = open(settings.REPORT_DIR + '/' + str(filename), 'rb')
            response = FileResponse(file)
            response['Content-Type'] = 'application/octet-stream'

            response[
                'Content-Disposition'] = "attachment;filename=" + filename.encode(
                    "utf-8").decode('ISO-8859-1')
            return response
        else:
            if group == "All":
                # logging.info("ALL")
                ams = Authenticated_Machine.objects.all()
            else:
                # logging.info(group)
                # logging.info(type(group))
                # logging.info(str(group))
                ams = Authenticated_Machine.objects.filter(
                    mygroup__name=str_group)

            for am in ams:
                offline_event = None
                logs = LogsEden.objects.defer(
                    'cpuUsage', 'diskUsage', 'memJson', 'swapMemJson',
                    'netJson', 'procByCpu', 'procByMem').filter(
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
                            ), ).order_by('datetime')

                lastlog = []
                logging.info("am : %s" % am.hostName)
                for log in logs.iterator():
                    # logging.info("lastlog : %s" % lastlog)
                    # logging.info("lastlog before : %s" % lastlog)
                    err_list, err_dict, lastlog = log.merge_event_type(lastlog)
                    # logging.info("lastlog after : %s" % lastlog)
                    # logging.info(log.datetime)
                    # lastlog = []

                    if err_list:
                        # for event in log.get_event():
                        #     lastlog.append(event.get("eventtype"))
                        for ev in err_list:
                            # A1 ~ A2
                            # logging.info("log.get_event() : {}".format(ev))
                            if "CRITICAL" in ev:
                                a1_critical += 1
                                a2_events.append(
                                    a2_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
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
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "CPU_MAJOR" in ev:
                                b2_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "CPU_WARNING" in ev:
                                logging.info("b3 %s" % log.datetime)
                                b3_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "MEM_CRITICAL" in ev:
                                b4_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "MEM_MAJOR" in ev:
                                b5_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "MEM_WARNING" in ev:
                                b6_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "SWAP_CRITICAL" in ev:
                                b7_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "SWAP_MAJOR" in ev:
                                b8_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "SWAP_WARNING" in ev:
                                b9_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "DISK_CRITICAL" in ev:
                                b10_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "DISK_MAJOR" in ev:
                                b11_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))
                            elif "DISK_WARNING" in ev:
                                b12_events.append(
                                    b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime,
                                        ev,
                                        err_dict.get(ev),
                                    ))

                            # C
                            if "OFFLINE" in ev:
                                if offline_event and offline_event.datetime.strftime(
                                        "%Y-%m-%d, %H:%M:%S"
                                ) == log.datetime.astimezone().strftime(
                                        "%Y-%m-%d, %H:%M:%S"):
                                    print("same offline event : {}".format(
                                        offline_event.datetime))
                                    pass
                                else:
                                    offline_event = b_event(
                                        log.authenticated_machine.hostName,
                                        log.datetime.astimezone(),
                                        ev,
                                        err_dict.get(ev),
                                    )
                                    print("diff offline event : {}".format(
                                        offline_event.datetime))

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
            # # for b3 in b3_events:
            # #     logging.info("b3_event %s" % b3.datetime)

            # c1_offline_rate = (c1_offline_hour * 60 + c1_offline_min) \
            #     / (c1_all_avail_hour * 60)
            # c1_availibility = round(1 - c1_offline_rate, 2) * 100

            return render(
                request,
                "daily_check_report.html",
                {
                    'date':
                    mydate,
                    'mygroup':
                    str_group,

                    # A
                    'a1_critical':
                    a1_critical,
                    'a1_major':
                    a1_major,
                    'a1_warning':
                    a1_warning,
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
                    sorted(offline_events, key=lambda s: s.datetime),

                    # C
                    # 'c1_availibility': c1_availibility,
                    # 'c2_event_list': c2_event_list,
                })


# DiskInfo --------------------------------------------------------------------
@login_required
# @profile
def diskInfo(request, url_hostID):
    logging.info("Enter function (diskInfo)")

    if request.method == "GET":
        try:
            am = Authenticated_Machine.objects.get(hostID=url_hostID)
            title = am
        except Exception:
            title = "Cannot find machine!"
            return render(request, "diskInfo.html", {"title": title})

        time_threshold = datetime.now().astimezone() - timedelta(hours=6)

        logs = LogsEden.objects.defer(
            'procByCpu', 'procByMem',
            'event').filter(authenticated_machine=am,
                            datetime__gt=time_threshold).union(
                                LogsSurviver.objects.defer(
                                    'procByCpu', 'procByMem', 'event').filter(
                                        authenticated_machine=am,
                                        datetime__gt=time_threshold)).order_by(
                                            '-datetime')[:100]

        usageList = []
        if not logs:
            return render(request, "latestlogbyID.html", {
                'am': am,
                'logs': logs
            })

        for log in logs.iterator():
            usageVec = {
                'cpu_usage': log.cpuUsage,
                'memory_usage': log.memUsage(),
                'swap_usage': log.swapUsage(),
                'disk_usage': log.diskUsage,
                'datetime': log.datetime,
            }
            usageList.append(usageVec)

        df = pd.DataFrame.from_records(usageList)
        # df['datetime'] = df['datetime'].dt.tz_convert(get_localzone())
        fig = plot_log_line_chart(df, am)
        plot_div = plot(fig,
                        output_type='div',
                        include_plotlyjs=True,
                        show_link=False)

        try:
            log = LogsEden.objects.filter(authenticated_machine=am).first()
            diskTable = am.get_disk_table().to_html(
                classes='table table-striped')
            # logging.info("disk Table : %s" % (diskTable))
            # procCpuTable = log.get_proc_cpu_table().to_html(
            #     classes='table table-striped')
            # procMemTable = log.get_proc_mem_table().to_html(
            #     classes='table table-striped')
        except Exception as e:
            title = "Cannot find log!"
            return render(request, "diskInfo.html", {"title": title})

    return render(
        request,
        "diskInfo.html",
        {
            "title": title,
            "diskTable": diskTable,
            "update_time": log.datetime,
            "proc_by_cpu": None,  #procCpuTable,
            "proc_by_mem": None,  #procMemTable,
            'plot_div': plot_div,
        })


# show latest log for every machine -------------------------------------------
@login_required
# @profile
def dashboard(request):
    logging.info("Enter function (dashboard)")

    check_offline()

    # logging.info("Enter /dashboard/")

    class StatusCount:

        def __init__(self):
            self.all = 0
            self.normal = 0
            self.error = 0
            self.offline = 0

    status_cnt = StatusCount()

    if request.method == "GET":
        ams = Authenticated_Machine.objects.only('id').order_by(
            "first_warning_time", "mygroup", "hostName")

    if request.method == "POST":
        # search rule
        # search tab: search value
        # search tab: hostname, group, warning_time
        # search value: web1, ungrouped, < 10 mins
        search = request.POST.get('search')
        # TODO: finish search pattern logic
        # search_p = {}
        # for pattern in search.replace(' ', '').split(';'):
        #     index = pattern.index(':')
        #     search_p[pattern[0:index]] = pattern[index + 1:]
        # logging.info(f"search pattern: {search_p}")

        if search == "" or search == ' ':
            ams = Authenticated_Machine.objects.only('id').order_by("mygroup")

        else:
            ams = Authenticated_Machine.objects.filter(
                hostName__icontains=search).union(
                    Authenticated_Machine.objects.filter(
                        hostID__icontains=search),
                    Authenticated_Machine.objects.filter(
                        mygroup__name__icontains=search).order_by("mygroup"))

    if ams is None:
        logging.info('No machine registered!')
        return render(request, "dashboard.html", {})

    # logging.info("/dashboard/ ams exists")

    errors = []
    logs = []

    status_cnt.all = ams.count()

    for am in ams:

        log = LogsEden.objects.defer(
            'cpuUsage', 'diskUsage', 'memJson', 'swapMemJson', 'netJson',
            'procByCpu',
            'procByMem').filter(authenticated_machine=am).latest("datetime")

        if not log:
            # logging.info("/dashboard/ no latest log in %s" % (str(am)))
            return render(request, "dashboard.html", {})
        elif (log):
            # Error msg
            if am.bypass_email != 1:
                if (log.get_event()):
                    status_cnt.error += 1
                    errors.append(log)
                    logs.append(log)
                else:
                    status_cnt.normal += 1
                    logs.append(log)
            else:
                status_cnt.normal += 1
                logs.append(log)

        # if authenticated macheine is offline for one day
        else:
            status_cnt.error += 1
            tmp_log = LogsEden(authenticated_machine=am)
            tmp_log.event = {
                'eventtype': 'OFFLINE',
                'msg': 'OFFLINE for over one day'
            }
            errors.append(tmp_log)
            logs.append(tmp_log)

    # logging.info("/dashboard/ finish querying logs")
    # logging.info(f"logs : {log.memJson}")
    # logging.info("errors : %s" % errors)

    return render(request, "dashboard.html", {
        'logs': logs,
        'errors': errors,
        'status_cnt': status_cnt
    })


# 收 Log ----------------------------------------------------------------------
# @profile
@csrf_exempt
def post_log(request):
    if request.method == "POST":
        data = json.loads(request.body)
        # logging.info(f"request.body : {data}")
        rDatetime = data['datetime']
        rHostJson = data['host_info']
        rHostID = rHostJson['hostId']
        tmpDict = {}
        disk_policy_dict = {}
        # Trim disk partition info
        tmpDiskJson = data['disk_partitions']
        #tmpDiskJson = [x for x in tmpDiskJson if (x['total'] != 0 and x['used'] != 0 and x['device'] != "tmpfs" and x['device'].find("/dev/loop") > 0 and x['device'] != "overlay")]
        tmpDiskJson = [
            x for x in tmpDiskJson
            if (x['total'] != 0 and x['used'] != 0 and x['fstype'] != "tmpfs"
                and "/dev/loop" not in x['device'] and x['device'] != "overlay"
                and x['device'] != "cm_processes" and "nfs" not in x['fstype']
                and "cmprocesses" not in x['device']
                and "/var/lib/origin" not in x['mountpoint']
                and "/var/lib/docker" not in x['mountpoint']
                and "/var/lib/kubelet" not in x['mountpoint'] and "/mnt" not in
                x['mountpoint'] and "/media" not in x['mountpoint']
                and "/source" not in x['mountpoint'] and x['fstype'] != "nfs")
            # and "/var/lib/containers" not in x['mountpoint'])
        ]
        # logging.info("filter disk json : %s" % (tmpDiskJson))
        # 2022/03/21 format the DiskJson
        # for tmp in tmpDiskJson:
        #     tmp['total'] = sizeof_fmt(tmp['total'])
        #     tmp['used'] = sizeof_fmt(tmp['used'])
        #     tmp['free'] = sizeof_fmt(tmp['free'])
        #     tmpDiskUsage = round(tmp['usedPercent'], 2)
        #     tmpDiskMount = str(tmp['mountpoint'])
        #     tmpDict[str(tmpDiskMount)] = tmpDiskUsage
        #     disk_policy_str = disk_policy_str + "'%s': {'Pass:': %s, 'Warning': %s, 'Major': %s, 'Critical': %s}, " % (tmpDiskMount, 0, DEFAULT_WARNING, DEFAULT_MAJOR, DEFAULT_CRITICAL)
        # disk_policy_str = disk_policy_str.rstrip(", ")
        #     # disk_policy_str.rstrip(",")
        # disk_policy_str = disk_policy_str + "}"
        # disk_policy_dict[tmpDiskMount] = {
        #         "Pass": 0,
        #         "Warning": DEFAULT_WARNING,
        #         "Major": DEFAULT_MAJOR,
        #         "Critical": DEFAULT_CRITICAL
        #     }
        # print(tmpDiskJson)
        # print(tmpDiskJson['used'])
        # print(tmpDiskJson['free'])

        # for tmp in tmpDiskJson:
        #         tmpDiskUsage = round(tmp['usedPercent'], 2)
        #         tmpDiskMount = str(tmp['mountpoint'])
        #         tmpDict[str(tmpDiskMount)] = tmpDiskUsage
        # logging.info("change disk json : %s" % (tmpDiskJson))

        am_set = Authenticated_Machine.objects.filter(hostID=rHostID)

        if (am_set.count() > 0):
            disk_policy_str = "{"
            am = am_set[0]
            am.hostUptime = rHostJson['uptime']
            am.hostName = rHostJson['hostname'].split('.')[0]
            am.diskJson = tmpDiskJson

            for tmp in tmpDiskJson:
                tmp['total'] = sizeof_fmt(tmp['total'])
                tmp['used'] = sizeof_fmt(tmp['used'])
                tmp['free'] = sizeof_fmt(tmp['free'])
                tmpDiskUsage = round(tmp['usedPercent'], 2)
                tmpDiskMount = str(tmp['mountpoint'])
                tmpDict[str(tmpDiskMount)] = tmpDiskUsage
                disk_policy_str = disk_policy_str + "'%s': {'Pass': %s, 'Major': %s, 'Warning': %s, 'Critical': %s}, " % (
                    tmpDiskMount, 0, DISK_MAJOR, DISK_WARNING, DISK_CRITICAL)
            disk_policy_str = disk_policy_str.rstrip(", ")
            # disk_policy_str.rstrip(",")
            disk_policy_str = disk_policy_str + "}"

            # partition disk
            # logging.info("*" * 40)
            # diff_disk = eval(str(am.disk_policy)).keys() ^ eval(str(disk_policy_str)).keys()
            diff_disk = eval(str(disk_policy_str)).keys() - eval(
                str(am.disk_policy)).keys()
            if diff_disk:
                logging.info('add the new mountpoint')
                am.disk_policy = eval(str(am.disk_policy))
                # am.disk_policy = eval(str(am.disk_policy_str))
                for mp in diff_disk:
                    am.disk_policy[mp] = {
                        "Pass": 0,
                        "Warning": DISK_WARNING,
                        "Major": DISK_MAJOR,
                        "Critical": DISK_CRITICAL
                    }

            # am.disk_policy = disk_policy_str
            # am.cpu_policy = {
            #         "Pass": 0,
            #         "Warning": DEFAULT_WARNING,
            #         "Major": DEFAULT_MAJOR,
            #         "Critical": DEFAULT_CRITICAL
            #     }
            # am.memory_policy = {
            #         "Pass": 0,
            #         "Warning": DEFAULT_WARNING,
            #         "Major": DEFAULT_MAJOR,
            #         "Critical": DEFAULT_CRITICAL
            #     }
            # am.swap_policy = {
            #         "Pass": 0,
            #         "Warning": DEFAULT_WARNING,
            #         "Major": DEFAULT_MAJOR,
            #         "Critical": DEFAULT_CRITICAL
            #     }
            # logging.info("am.diskJson : %s" % (am.diskJson))
            # am.disk_policy = disk_policy_dict
            am.last_log_update = make_aware(
                datetime.strptime(rDatetime, '%Y-%m-%d %H:%M:%S'))
            am.save()
        else:
            disk_policy_str = "{"
            try:
                g = MyGroup.objects.get(name="ungrouped")
            except Exception:
                g = MyGroup.objects.create(name="ungrouped")

            for tmp in tmpDiskJson:
                tmpDiskUsage = round(tmp['usedPercent'], 2)
                tmpDiskMount = str(tmp['mountpoint'])
                tmpDict[str(tmpDiskMount)] = tmpDiskUsage
                disk_policy_str = disk_policy_str + "'%s': {'Pass': %s, 'Warning': %s, 'Major': %s, 'Critical': %s }, " % (
                    tmpDiskMount, 0, DISK_WARNING, DISK_MAJOR, DISK_CRITICAL)
                # disk_policy_dict[tmpDiskMount] = {
                #     "Pass": 0,
                #     "Warning": DEFAULT_WARNING,
                #     "Major": DEFAULT_MAJOR,
                #     "Critical": DEFAULT_CRITICAL
                # }

            disk_policy_str = disk_policy_str.rstrip(", ")
            # disk_policy_str.rstrip(",")
            disk_policy_str += "}"
            # logging.info("round disk json : %s" % (tmpDiskJson))
            ### disk policy = "{'mountpoint1': {'Pass': 0, 'Warning': DEFAULT_WARNING, 'Major': DEFAULT_MAJOR, 'Critical': DEFAULT_CRITICAL},
            # 'mountpoint2': {'Pass': 0, 'Warning': DEFAULT_WARNING, 'Major': DEFAULT_MAJOR, 'Critical': DEFAULT_CRITICAL}}"
            am = Authenticated_Machine.objects.create(
                hostName=rHostJson['hostname'],
                hostOS=rHostJson['os'] + ' ' + rHostJson['platformVersion'],
                hostID=rHostID,
                cpuCount=data['cpu_count'],
                mygroup=g,
                hostUptime=rHostJson['uptime'],
                diskJson=tmpDiskJson,
                # disk_policy=disk_policy_dict,
                disk_policy=disk_policy_str,
            )
            logging.info('New authenticated_machine added')

        # Create New Log
        # logging.info("info tmp_dict : %s" % (tmpDict))
        # logging.DEBUG("tmp_dict" % (tmpDict))
        newLog = LogsEden.objects.create(
            authenticated_machine=am,
            cpuUsage=float(data['cpu_usage']),
            diskUsage=tmpDict,
            # memJson=data['mem_stat']['usedPercent'],
            memJson=float(data['memory_usage']),
            # swapMemJson=data['swap_mem_stat']['usedPercent'],
            swapMemJson=float(data['swap_usage']),
            # procByCpu=data['proc_by_cpu'],
            # procByMem=data['proc_by_mem'],
            datetime=make_aware(
                datetime.strptime(rDatetime, '%Y-%m-%d %H:%M:%S')))
        create_err_msg(newLog, am)

        response = HttpResponse()
        response['refresh_time_interval'] = am.refresh_time_interval

        return response
    else:
        # print(HttpResponse())
        return HttpResponse(status=500)


# request the api for python agent


def post_log_python(request):
    if request.method == "POST":
        data = json.loads(request.body)
        rDatetime = data['hostime']
        rLinuxDis = data['linuxDis']
        # rHostJson = data['host_info']
        rHostID = data['hostid']
        tmpDict = {}
        disk_policy_dict = {}
        # Trim disk partition info
        tmpDiskJson = data['diskall']
        #tmpDiskJson = [x for x in tmpDiskJson if (x['total'] != 0 and x['used'] != 0 and x['device'] != "tmpfs" and x['device'].find("/dev/loop") > 0 and x['device'] != "overlay")]
        tmpDiskJson = [
            x for x in tmpDiskJson
            if (x['total'] != 0 and x['used'] != 0 and x['device'] != "tmpfs"
                and "/dev/loop" not in x['device'] and x['device'] != "overlay"
                and "/var/lib/origin" not in x['mountpoint']
                and "/var/lib/docker" not in x['mountpoint'])
        ]

        am_set = Authenticated_Machine.objects.filter(hostID=rHostID)
        # if am_set[0].disk_policy['/'].get('Critical') == "":
        # for tmpDiskInfo in tmpDiskJson:
        #     tmpDiskUsage = round(tmpDiskInfo['usedPercent'],2)
        #     tmpDiskMount = str(tmpDiskInfo['mountpoint'])
        #     tmpDict[str(tmpDiskMount)] = tmpDiskUsage
        #     disk_policy_dict[tmpDiskMount] = {
        #         "Pass": 0, "Warning": DEFAULT_WARNING, "Major": DEFAULT_MAJOR, "Critical": DEFAULT_CRITICAL
        #     }
        # if
        #     am = am_set[0]
        #     am.hostUptime = rHostJson['uptime']
        #     am.hostName = rHostJson['hostname']
        #     am.diskJson = tmpDiskJson
        #     am.disk_policy = disk_policy_dict
        #     am.last_log_update = make_aware(
        #         datetime.strptime(rDatetime, '%Y-%m-%d %H:%M:%S')
        #     )
        #     am.save()
        # for tmpDiskInfo in tmpDiskJson:
        #     tmpDiskUsage = round(tmpDiskInfo['usedPercent'],2)
        #     tmpDiskMount = str(tmpDiskInfo['mountpoint'])
        #     tmpDict[str(tmpDiskMount)] = tmpDiskUsage
        #     disk_policy_dict[tmpDiskMount] = {
        #         "Pass": 0, "Warning": DEFAULT_WARNING, "Major": DEFAULT_MAJOR, "Critical": DEFAULT_CRITICAL
        #     }
        # if am_set:
        #     # if queryset is empty, couldn't specify key for the dictionary.
        #     if '/' in am_set[0].disk_policy:
        #         if am_set[0].disk_policy['/'].get('Critical') == "":
        #             am = am_set[0]
        #             am.hostUptime = rHostJson['uptime']
        #             am.hostName = rHostJson['hostname']
        #             am.diskJson = tmpDiskJson
        #             am.disk_policy = disk_policy_dict
        #             am.last_log_update = rDatetime
        #             am.save()
        #     # old data of the am.disk_policy maybe empty values
        #     else:
        #         am = am_set[0]
        #         am.hostUptime = rHostJson['uptime']
        #         am.hostName = rHostJson['hostname']
        #         am.diskJson = tmpDiskJson
        #         am.disk_policy = disk_policy_dict
        #         am.last_log_update = rDatetime
        #         am.save()

        if (am_set.count() > 0):
            am = am_set[0]
            am.hostUptime = data['uptime']
            am.hostName = data['hostname']
            am.diskJson = tmpDiskJson
            # am.disk_policy = disk_policy_dist
            am.last_log_update = make_aware(
                datetime.strptime(rDatetime, '%Y-%m-%d %H:%M:%S'))
            am.save()
        else:
            try:
                g = MyGroup.objects.get(name="ungrouped")
            except Exception:
                g = MyGroup.objects.create(name="ungrouped")

            for tmp in tmpDiskJson:
                tmpDiskUsage = round(tmp['percent'], 2)
                tmpDiskMount = str(tmp['mountpoint'])
                tmpDict[str(tmpDiskMount)] = tmpDiskUsage
                disk_policy_dict[tmpDiskMount] = {
                    "Pass": 0,
                    "Warning": DEFAULT_WARNING,
                    "Major": DEFAULT_MAJOR,
                    "Critical": DEFAULT_CRITICAL
                }

            am = Authenticated_Machine.objects.create(
                hostName=data['hostname'],
                hostOS=rLinuxDis[0].split(' ')[0] +
                rLinuxDis[0].split(' ')[1] + " " + rLinuxDis[1],
                hostID=rHostID,
                cpuCount=data['total_cpucores'],
                mygroup=g,
                hostUptime=data['uptime'],
                diskJson=tmpDiskJson,
                disk_policy=disk_policy_dict,
            )
            logging.info('New authenticated_machine added')

        # Create New Log
        newLog = LogsEden.objects.create(authenticated_machine=am,
                                         cpuUsage=int(data['totalcpuusage']),
                                         diskUsage=tmpDict,
                                         memJson=data['memoryusage'],
                                         swapMemJson=data['swapusage'],
                                         procByCpu=data['cpuprocess'],
                                         procByMem=data['memoryprocess'],
                                         datetime=make_aware(
                                             datetime.strptime(
                                                 rDatetime,
                                                 '%Y-%m-%d %H:%M:%S')))
        create_err_msg(newLog, am)

        response = HttpResponse()
        response['refresh_time_interval'] = am.refresh_time_interval

        return response
    else:
        return HttpResponse(status=500)


# Assign group simotaniusly
# @profile
def assign_group(request):
    groups = MyGroup.objects.only("name").order_by('name')

    ams = Authenticated_Machine.objects.only("id",
                                             "hostName").order_by('mygroup')
    if (request.method == 'GET'):
        return render(request, "assign_group.html", {
            "groups": groups,
            "ams": ams,
        })

    elif (request.method == 'POST'):
        out_string = ''

        to_group = request.POST.get('to_group')
        from_pk = [int(i) for i in request.POST.getlist('from')]

        to_group = MyGroup.objects.get(name=to_group)

        for am_pk in from_pk:
            am = Authenticated_Machine.objects.get(pk=am_pk)
            am.mygroup = to_group
            am.save()
            out_string = out_string + (str(am) + ', <br>')

        out_string = out_string + '<br>-----moved!------'

        return render(request, "assign_group.html", {
            "groups": groups,
            "ams": ams,
        })


# def popup(request):
#     logging.info("enter view popup")
#     if request.method == 'GET':
#         return render(request, '/popup.html')

#     elif request.method == 'POST':
#         time_interval = request.POST.get('time_interval')
#         return render(request, '/popup.html', {'time_interval': time_interval})


# def change_group(request):
@login_required
def customized_report(request):
    ams = Authenticated_Machine.objects.all()
    if (request.method == "GET"):
        return render(request, "customized_report.html", locals())
    elif (request.method == "POST"):
        str_hostName = request.POST.get("hostName")
        str_start_date = request.POST.get("start_date")
        str_end_date = request.POST.get("end_date")
        str_view = request.POST.get("view")

        am = Authenticated_Machine.objects.get(hostName=str_hostName)

        start_date = make_aware(datetime.strptime(str_start_date, "%Y-%m-%d"))
        end_date = make_aware(datetime.strptime(str_end_date, "%Y-%m-%d"))

        # Error Check
        if (start_date > end_date):
            error = "輸入錯誤：結束日期不能先於起始日期"
            messages.error(request, error)
            return render(request, "customized_report.html",
                          {'my_hostName': str_hostName})

        if (start_date > make_aware(datetime.now())
                or end_date > make_aware(datetime.now())):
            error = "輸入錯誤：起始日期不能先於現在日期"
            messages.error(request, error)
            return render(request, "customized_report.html",
                          {'my_hostName': str_hostName})

        start_datetime = make_aware(datetime.combine(start_date, time(0, 0)))
        end_datetime = make_aware(datetime.combine(end_date, time(23, 59)))

        title = "自訂搜尋：%s~%s" % (str_start_date, str_end_date)
        filename = f"{am.hostName}-自訂搜尋-{str_start_date}-{str_end_date}.pdf"

        if str_view == "all":
            logs = get_logs_all(am, start_datetime, end_datetime)
        elif str_view == "hour":
            logs = get_logs_by_hour(am, start_datetime, end_datetime)
        elif str_view == "day":
            logs = get_logs_by_date(am, start_datetime, end_datetime)
        else:
            error = 'Unexpected error!'
            messages.error(request, error)
            return render(request, "customized_report.html", {})

        if logs is None:
            title = "時間內找不到日誌檔"
            messages.error(request, title)
            return render(request, 'customized_report.html', {})

        usageList = []
        if str_view == "all":
            for log in logs:
                usageDict = {
                    'cpu_usage':
                    log.cpuUsage,
                    'memory_usage':
                    log.memUsage(),
                    'swap_usage':
                    log.swapUsage(),
                    'datetime':
                    log.datetime.astimezone(
                        timezone(timedelta(hours=8), "Asia/Taipei"))
                }
                logging.info(usageDict['datetime'])
                usageList.append(usageDict)
        elif str_view == "hour" or str_view == "day":
            for log in logs:
                usageDict = {
                    'cpu_usage':
                    log.avg_cpu_usage,
                    'memory_usage':
                    log.avg_memory_usage,
                    'swap_usage':
                    log.avg_swap_usage,
                    'datetime':
                    log.datetime.astimezone(
                        timezone(timedelta(hours=8), "Asia/Taipei"))
                }
                usageList.append(usageDict)

        logging.info(usageList[0]['datetime'])
        # logging.info(type(usageList[0]['datetime']))
        df = pd.DataFrame.from_records(usageList)
        # df['datetime'] = df['datetime'].dt.tz_convert(get_localzone())

        # plot
        fig = plot_log_line_chart(df, am)
        plot_div = plot(fig,
                        output_type='div',
                        include_plotlyjs=True,
                        show_link=False)
    if str_view == "all":
        return render(
            request, "report_single_log.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 0
            })
    elif str_view == "hour":
        return render(
            request, "report_by_hour.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 1,
                'url_interval': 1,
                'url_hostID': am.hostID,
                'filename': filename
            })
    elif str_view == "day":
        return render(
            request, "report_by_date.html", {
                'logs': logs,
                'title': title,
                'am': am,
                'plot_div': plot_div,
                'mode': 0
            })


@login_required
def customized_datereport(request):

    group_dict = {}
    group_list = []

    mygroups = MyGroup.objects.all()
    for group in mygroups:
        if Authenticated_Machine.objects.filter(mygroup=group):
            group_list.append(group)
        for g_am in Authenticated_Machine.objects.filter(mygroup=group):
            group_dict.setdefault(group.name, []).append(g_am.hostName)

    group_list.reverse()
    str_date = ''
    str_month = ''
    str_year = ''

    if request.method == "GET":
        logging.info("Enter function (customized_datereport) : GET")

        return render(
            request, "customized_datereport.html", {
                'str_date': str_date,
                'str_month': str_month,
                'str_year': str_year,
                'mygroups': group_list,
                'group_dict': group_dict
            })

    elif request.method == "POST":
        logging.info("Enter function (customized_datereport) : POST")
        check_cnt = 0
        str_hostName = request.POST.get("hostName")
        str_date = request.POST.get("start_date")
        str_month = request.POST.get("end_date")
        str_year = request.POST['yearpicker']
        logging.info(f"datepicker: {str_date}")
        logging.info(f"monthpicker: {str_month}")

        if str_date != '':
            check_cnt += 1
            date_type = str_date
            int_url_interval = 1
        if str_month != '':
            check_cnt += 1
            date_type = str_month
            int_url_interval = 30
        if str_date == '' and str_month == '':
            check_cnt += 1
            date_type = str_year
            int_url_interval = 365

        if check_cnt > 1:
            error = '選取時區發生錯誤!'
            return render(request, "customized_datereport.html", locals())

        am = Authenticated_Machine.objects.get(hostName=str_hostName)
        start, end, title = get_time_threshold_2(int_url_interval, am,
                                                 date_type)
        logging.info("custom_datereport: start : %s, end : %s " % (start, end))
        logs = None

        # 日報表
        if (int_url_interval == 1):
            logs = get_logs_by_hour(am, start, end)

        # 週/月報表 改成一天一筆資料
        elif int_url_interval == 30:
            logs = get_logs_by_date(am, start, end)

        elif int_url_interval == 365:
            logs = get_logs_by_month(am, start, end)

        try:
            logs[0]
        except Exception:
            title = "此時段" + str(am) + "無資料"
            return render(request, "report_by_hour.html", {
                'logs': logs,
                'title': title,
                'am': am
            })

        usageList = []
        if logs is None:
            logging.info("(saved-report) No logs.")
            return render(request, 'report_by_hour.html', {
                'am': am,
                'logs': logs
            })

        for log in logs:
            logging.info(f"{log.datetime}: {log.avg_cpu_usage}")
            logging.info(type(log.datetime))
            usageDict = {
                'cpu_usage': log.avg_cpu_usage,
                'memory_usage': log.avg_memory_usage,
                'swap_usage': log.avg_swap_usage,
                'datetime': log.datetime
            }
            usageList.append(usageDict)
        # print(usageList)

        df = pd.DataFrame.from_records(usageList)
        # df['datetime'] = df['datetime'].dt.tz_convert(get_localzone())

        # plot
        fig = plot_log_line_chart(df, am)
        plot_div = plot(fig,
                        output_type='div',
                        include_plotlyjs=True,
                        show_link=False)

        html_var = {
            'logs': logs,
            'title': title,
            'am': am,
            'plot_div': plot_div,
            'url_interval': int_url_interval,
            'url_hostID': am.hostID,
            'cpu_policy': eval(str(am.cpu_policy)),
            'mem_policy': eval(str(am.memory_policy)),
            'swap_policy': eval(str(am.memory_policy))
        }
        logging.info("Enter to product the filename")
        pdf_info = {'logs': logs, 'title': title, 'am': am}
        if (int_url_interval == 1):
            filename = f"SYSMO-{str(am.hostName)}-{start.strftime('%Y%m%d')}-Performance"

            if request.POST.get('dl_csv'):
                response = log_report_generate_csv(filename, logs,
                                                   int_url_interval)
                return response

            if request.POST.get('dl_pdf'):
                logging.info("produce the PDF file")
                response = log_report_generate_pdf(filename, html_var)
                return response
            html_var['filename'] = filename + '.pdf'
            return render(request, "report_by_hour.html", html_var)
        elif int_url_interval == 30:
            filename = f"SYSMO-{str(am.hostName)}-{start.strftime('%Y')}-{start.strftime('%m')}-Performance"

            if request.POST.get('dl_csv'):
                response = log_report_generate_csv(filename, logs,
                                                   int_url_interval)
                return response

            if request.POST.get('dl_pdf'):
                response = log_report_generate_pdf(filename, html_var)
                return response
            html_var['filename'] = filename + '.pdf'
            return render(request, "report_by_date.html", html_var)

        elif int_url_interval == 365:
            filename = f"SYSMO-{str(am.hostName)}-{start.strftime('%Y')}-Performance"

            if request.POST.get('dl_csv'):
                response = log_report_generate_csv(filename, logs,
                                                   int_url_interval)
                return response

            if request.POST.get('dl_pdf'):
                response = log_report_generate_pdf(filename, html_var)
                return response
            html_var['filename'] = filename + '.pdf'
            return render(request, "report_by_date.html", html_var)

    return render(request, 'customized_datereport.html', locals())


def log_report_generate_csv(filename, logs, interval):
    if interval == 1:
        format_date = "%Y-%m-%d %H:%M:%S"
    else:
        format_date = "%Y-%m-%d"

    output = []
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = 'attachment; filename=' + filename.encode(
            "utf-8").decode('ISO-8859-1') + '.csv'

    response.write(u'\ufeff'.encode('utf8'))

    writer = csv.writer(response)
    #Header
    writer.writerow([
        '時間區間', 'Cpu 平均值', 'Cpu 最大值', 'Mem 平均值', 'Mem 最大值', 'Swap 平均值',
        'Swap 最大值'
    ])
    for log in logs:
        output.append([
            log.datetime, log.avg_cpu_usage, log.max_cpu_usage,
            log.avg_memory_usage, log.max_memory_usage, log.avg_swap_usage,
            log.max_swap_usage
        ])
    #CSV Data
    writer.writerows(output)
    return response


def log_report_generate_pdf(filename, html_var):
    """Create the PDF accroding from html_var and filename arguments.

    Args:
        html_var (dict): The information about painting pdf file.
                        {
                            title(str): The infomation about the file,
                            am(obj): Machine infomation,
                            logs(obj): The information about log object,

                        }
        filename (str): The filename that you want to created.

    Returns: sysmo/logserver/views.py
        response: pdf download
    """
    # logging.info(f"args: {args}")
    # logging.info(f"kwargs: {kwargs}")
    # html_var = kwargs['html_var']
    logging.info([log.datetime for log in html_var.get('logs')])
    logging.info("(log_report_generate_pdf) Enter function.")
    # logging.info(f"html_var : {html_var}")
    env = Environment(loader=FileSystemLoader(settings.TEMPLATE_DIR))

    template = env.get_template("pdf_report.html")
    html_out = template.render(html_var)

    HTML(string=html_out, encoding="utf-8").write_pdf(
        "%s/%s" % (settings.REPORT_DIR, filename + ".pdf"),
        stylesheets=[CSS(settings.STATIC_DIR + '/css/pdf_check_report.css')])

    try:
        file = open(settings.REPORT_DIR + '/' + filename + '.pdf', 'rb')
    except Exception as e:
        logging.error(e)

    response = FileResponse(file)
    response['Content-Type'] = 'application/octet-stream'
    response[
        'Content-Disposition'] = 'attachment;filename=' + filename + '.pdf'

    return response


def delete_ams(request, url_hostName):
    if request.method == "POST":
        try:
            am = Authenticated_Machine.objects.filter(
                hostName__icontains=url_hostName)
            if am.count() > 1:
                return HttpResponse(status=400)
            am[0].delete()

            return HttpResponse(status=200)
        except Exception as e:
            logging.info(str(e))
            return HttpResponse(status=400)


def am_report_generate_csv(request):
    if request.method == "GET":
        ams = Authenticated_Machine.objects.only("hostName", "hostID", "id",
                                                 "serverIP").all()
        filename = "Host_List"

        output = []
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = 'attachment; filename=' + filename.encode(
                "utf-8").decode('ISO-8859-1') + '.csv'

        response.write(u'\ufeff'.encode('utf8'))

        writer = csv.writer(response)
        #Header
        writer.writerow(['Hostname', 'Host ID', 'ID', 'Server IP'])
        for am in ams:
            output.append([am.hostName, am.hostID, am.id, am.serverIP])
        #CSV Data
        writer.writerows(output)
        return response


def check_date(*args):
    date = [365, 30, 1]
    cnt = 0
    for arg in args:
        if arg == None or arg == "":
            cnt += 1
            continue
        date_type = arg
    return date_type, date[cnt]


# HANDLE error404


def page_not_found(request, exception, template_name='errors/page_404.html'):
    return render(request, template_name)


# @profile
# def static(request, url):

#     return render(request, "latestbymac.html", {
#         'am': am,
#         'logs': logs,
#         'plot_div': plot_div
#     })
