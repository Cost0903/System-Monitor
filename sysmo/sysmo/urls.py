"""sysmo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls import include, handler404  # re_path # url,
from django.conf.urls.static import static
from django.urls import path, re_path
from logserver import views

urlpatterns = [
    path('', views.dashboard),
    path('accounts/', include('django.contrib.auth.urls')),
    path('customized_report/', views.customized_report),
    path('customized_datereport/', views.customized_datereport),
    re_path(r'^delete_ams/(?P<url_hostName>[\w\-]+)/$', views.delete_ams),
    path('get_ams/', views.am_report_generate_csv),
    path('admin/', admin.site.urls),
    path('dashboard/', views.dashboard),
    re_path(r'^diskInfo/(?P<url_hostID>[\w\-]+)/$',
            views.diskInfo,
            name="diskInfo"),
    re_path(r'^latestlogbyID/(?P<url_hostID>[\w\-]+)/$',
            views.latestlogbyID,
            name="latestlogbyID"),

    # select authenticated machine
    path('query_check_report/', views.query_check_report),

    # self-query-report
    # re_path(r'^set-query/(?P<url_hostID>[\w\-]+)/(?P<url_interval>\d{0,3})/$',
    #         views.set_query_for_self_defined_report),
    # path('custom-query-report/', views.custom_query_report),

    # defined report
    # re_path(
    #     r'^saved-report/(?P<url_hostID>[\w\-]+)/(?P<url_interval>\d{0,3})/$',
    #     views.saved_report),

    # post log
    path('post_log/', views.post_log),
    # path('post_log_python/', views.post_log_python),
    path('assign_group/', views.assign_group),

    # 報表下載 (Report Download)
    re_path(r'reports/(?P<url_interval>\d{0,3})/(?P<url_hostID>[\w\-]+)/',\
            views.reports,
            name="reports"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = views.page_not_found
