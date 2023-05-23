# from django.urls import path, include
# from . import views
# from django.conf.urls.static import static

# urlpatterns = [
#     path('', views.dashboard_layer1),
#     path('accounts/', include('django.contrib.auth.urls')),
#     path('customized_report/', views.customized_report),
#     path('customized_datereport/', views.customized_datereport),
#     path(r'^delete_ams/(?P<url_hostName>[\w\-]+)/$', views.delete_ams),
#     path('get_ams/', views.am_report_generate_csv),
#     path(r'^dashboard/$', views.dashboard_layer1),
#     path(r'^dashboard2/(?P<url_hostID>[\w\-]+)/$', views.dashboard_layer2),
#     path(r'^latestbymac/(?P<url_hostID>[\w\-]+)/$', views.latestbymac),

#     # select authenticated machine
#     path(r'^query_check_report/$', views.query_check_report),

#     # self-query-report
#     path(r'^set-query/(?P<url_hostID>[\w\-]+)/(?P<url_interval>\d{0,3})/$',
#          views.set_query_for_self_defined_report),
#     path(r'^custom-query-report/$', views.custom_query_report),

#     # defined report
#     path(r'^select-machine/(?P<nextpage>[\w\-]+)/(?P<url_interval>\d{0,3})/$',
#          views.select_machine),
#     path(r'^saved-report/(?P<url_hostID>[\w\-]+)/(?P<url_interval>\d{0,3})/$',
#          views.saved_report),

#     # post log
#     # path(r'^post_log/', views.post_log),
#     path(r'^post_log_python/', views.post_log_python),
#     path(r'^assign_group/', views.assign_group),

#     # 報表下載 (Report Download)
#     path(r'reports/(?P<url_interval>\d{0,3})/(?P<url_hostID>[\w\-]+)',
#          views.reports,
#          name="reports"),
# ]

# handler404 = views.page_not_found
