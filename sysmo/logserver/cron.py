from .scripts import check_offline, get_time_threshold, porter
from .scripts import pdf_report_generator_by_am, \
    pdf_report_generator_by_group, pdf_daily_check_report, pdf_daily_check_report_all
from .models import MyGroup, Authenticated_Machine
from .api import isms_file
from datetime import datetime, timedelta
from .scripts import send_report
import logging


# sync database ------------
def one_hour_refresh():
    porter()

def one_minute_refresh():
    check_offline()

# Reports ------------------
def send_daily_report():
    logging.debug("Enter function (send_daily_report)")
    ams = Authenticated_Machine.objects.all()
    daily_time = (datetime.now() - timedelta(days=1)).astimezone().strftime("%Y%m%d")
    groups = MyGroup.objects.all()
    filename = "銀行Linux每日作業檢核表-%s" % (daily_time)
    send_report(filename, "All", 100)
    return

def send_weekly_report():
    logging.debug("Enter function (send_weekly_report)")
    ams = Authenticated_Machine.objects.all()
    for am in ams:
        start, end, title = get_time_threshold(7,am)
        group = MyGroup.objects.filter(name=am.mygroup)
        filename = "SYSMO-%s-%s-%s-Performance" % (str(am.hostName, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
        send_report(filename, group, 7)
    return

def send_monthly_report():
    logging.debug("Enter function (send_monthly_report)")
    ams = Authenticated_Machine.objects.all()
    monthly_time = (datetime.now() - timedelta(days=datetime.now().day)).astimezone().strftime("%Y-%m")
    for am in ams:
        group = MyGroup.objects.filter(name=am.mygroup)
        filename = "SYSMO-%s-%s-Performance" % (str(am.hostName), monthly_time)
        send_report(filename, group, 30)
    return

def send_yearly_report():
    logging.debug("Enter function (send_monthly_report)")
    ams = Authenticated_Machine.objects.all()
    last_year = datetime.now().year - 1
    year_time = (datetime.now() - timedelta(days=datetime.now().day)).astimezone().strftime("%Y-%m")
    for am in ams:
        group = MyGroup.objects.filter(name=am.mygroup)
        filename = "SYSMO-%s-%s-Performance" % (str(am.hostName), last_year)
        send_report(filename, group, 365)
    return

def create_daily_report():
    # Daily report (Performance report)
    ams = Authenticated_Machine.objects.all()
    for am in ams:
        pdf_report_generator_by_am(am, 1)

    # Check report (Event report)
    groups = MyGroup.objects.all()
    for group in groups:
        if group.authenticated_machine_set.all() is not None:
            pdf_daily_check_report(group)

    pdf_daily_check_report_all("All")
    return

    # Send weekly report (Performance report)
def create_weekly_report():
    ams = Authenticated_Machine.objects.all()
    for am in ams:
        pdf_report_generator_by_am(am, 7)

    return

    # Send monthly report (Performance report)
def create_monthly_report():
    ams = Authenticated_Machine.objects.all()
    for am in ams:
        pdf_report_generator_by_am(am, 30)

    return

def create_yearly_report():
    ams = Authenticated_Machine.objects.all()
    for am in ams:
        pdf_report_generator_by_am(am, 365)
    return

# ISMS
    # Daily Sync to ISMS Server
def sync_isms():
    isms_file()
    return

# --------------------------
