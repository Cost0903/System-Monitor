from django.utils.safestring import mark_safe
from django.forms import Widget
import json
import logging
from ast import literal_eval
from django.contrib import admin
from django.shortcuts import render
from .models import MyGroup, Profile, Authenticated_Machine, AMDiskJsonField, MountPointJsonField, CommonPolicyJsonField
from django.utils.html import format_html, format_html_join
from django.http import HttpResponseRedirect
from django.db.models import JSONField
from django.template.loader import render_to_string
from django.forms import widgets
from django.conf import settings

# Register your models here.
admin.site.site_header = 'SysMo 後臺管理系統'
admin.site.site_title = 'SysMo 後臺管理'
admin.site.index_title = 'SysMo 後臺管理系統'

# def delete_selected(modeladmin, request, queryset):
#     if 'apply' in request.POST:
#         for obj in queryset:
#             obj.delete()
#         modeladmin.message_user(request,
#                                 "Deleted on {} qs.".format(queryset.count()))
#         return HttpResponseRedirect(request.get_full_path())
#     return render(request,
#                   'admin/delete_intermediate.html',
#                   context={
#                       'qs': queryset,
#                   })

# delete_selected.short_description = "Delete Selected Objects"


class JSONEditorWidget(Widget):

    def __init__(self, HTMLpath, attrs=None):
        self.template_name = HTMLpath

        super(JSONEditorWidget, self).__init__(attrs)
        # template_name = 'widget.html'
    def render(self, name, value, attrs=None, renderer=None):
        # print(value)
        try:
            value = literal_eval(json.loads(value))
        except Exception as e:
            value = literal_eval(value)
        context = {'value': value, 'name': name}
        print(context)

        return mark_safe(render_to_string(self.template_name, context))


class MyGroup_Admin(admin.ModelAdmin):
    list_display = ('get_group_name', 'get_mail_list', 'get_description')
    fields = ("name", "description", "mail")
    search_fields = ('name', )

    # autocomplete_fields = ['name']

    def get_group_name(self, obj):
        return obj.name

    def get_mail_list(self, obj):
        # return obj.mail
        return ",\n".join([p for p in obj.get_mail()])

    def get_description(self, obj):
        return obj.description

    get_group_name.short_description = '主機群組'
    get_mail_list.short_description = 'Email通知清單'
    get_description.short_description = 'Description'


admin.site.register(MyGroup, MyGroup_Admin)


class Profile_Admin(admin.ModelAdmin):
    list_display = ('get_username', 'get_email', 'get_group')
    fields = ('user', 'mygroup')
    # autocomplete_fields = ['mygroup']
    # readonly_fields = ('user',)
    # filter_vertical = ('mygroup', )
    filter_horizontal = ('mygroup', )

    # filter_horizontal

    def get_username(self, obj):
        return obj.user.username

    def get_email(self, obj):
        return obj.user.email

    def get_group(self, obj):
        return ",\n".join([p.name for p in obj.mygroup.all().order_by('name')])

    get_username.short_description = '使用者名稱'
    get_email.short_description = 'Email 帳號'
    get_group.short_description = '訂閱群組清單'


admin.site.register(Profile, Profile_Admin)


class PrettyJSONWidget(widgets.Textarea):

    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split('\n')]
            self.attrs['rows'] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs['cols'] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception as e:
            logging.info("Error while formatting JSON: {}".format(e))
            return super(PrettyJSONWidget, self).format_value(value)


class AM_Admin(admin.ModelAdmin):

    def has_add_permission(self, request, obj=None):
        return False

    list_per_page = settings.LIST_PER_PAGE

    fieldsets = (('主機資訊', {
        'fields': ('asset_ID', 'hostID', 'hostName', 'serverIP', 'hostOS',
                   'last_log_update')
    }), ('負責人', {
        'fields': ('depository_name', 'backup_name')
    }), ('告警Policy', {
        'fields': ('cpu_policy', 'memory_policy', 'swap_policy', 'diskJson',
                   'disk_policy', 'bypass_email', 'refresh_time_interval')
    }))

    # fields = ('asset_ID', 'hostName', 'serverIP', 'hostOS', ('depository_name', 'backup_name'), 'cpuCount', )
    readonly_fields = ("hostID", "hostOS", "cpuCount", "hostUptime",
                       "asset_ID", "serverIP", "depository_name", "backup_name"
                       )  # ,'cpu_vec', 'mem_vec', 'swap_vec', 'disk_vec'
    list_display = (
        'hostName',
        'mygroup',
        'bypass_email',
        'cpu_vec',
        'mem_vec',
        'swap_vec',  # 'disk_vec',
        'refresh_time_interval',  # 'cpu_vec', 'disk_vec'
        # alert_time
    )

    list_editable = ('bypass_email', 'refresh_time_interval'
                     )  # 'cpu_vec', 'disk_vec')
    search_fields = ('hostName', 'mygroup__name', 'hostID')

    # ----------------------------------------------------------------
    formfield_overrides = {
        AMDiskJsonField: {
            'widget': JSONEditorWidget("widget.html")
        },
        MountPointJsonField: {
            'widget': JSONEditorWidget('MountPointwidget.html')
        },
        CommonPolicyJsonField: {
            'widget': JSONEditorWidget('widget_policy.html')
        }
    }

    def cpu_vec(self, obj):
        trans_json = eval(str(obj.cpu_policy))
        return format_html(
            """
            <div>Warning : {}</div>
            <div>Major : {}</div>
            <div>Critical : {}</div>
            <div>Pass : {}</div>
            """,
            trans_json['Warning'],
            trans_json['Major'],
            trans_json['Critical'],
            trans_json['Pass'],
        )

    cpu_vec.short_description = 'CPU 告警(%)'

    def mem_vec(self, obj):
        trans_json = eval(str(obj.memory_policy))
        return format_html(
            """
            <div>Warning : {}</div>
            <div>Major : {}</div>
            <div>Critical : {}</div>
            <div>Pass : {}</div>
            """,
            trans_json['Warning'],
            trans_json['Major'],
            trans_json['Critical'],
            trans_json['Pass'],
        )

    mem_vec.short_description = 'MEMORY 告警(%)'

    def swap_vec(self, obj):
        trans_json = eval(str(obj.swap_policy))
        return format_html(
            """
            <div>Warning : {}</div>
            <div>Major : {}</div>
            <div>Critical : {}</div>
            <div>Pass : {}</div>
            """,
            trans_json['Warning'],
            trans_json['Major'],
            trans_json['Critical'],
            trans_json['Pass'],
        )

    swap_vec.short_description = 'SWAP 告警(%)'

    def disk_vec(self, obj):
        # result = ""

        result = format_html_join(
            '\n', """
                <div>MountPoint : {}</div>
                <div>Warning : {}</div>
                <div>Major : {}</div>
                <div>Critical : {}</div>
                <div>Pass : {}</div>
                <br>
            """, ((
                mountpoint,
                obj.disk_policy[mountpoint].get('Warning'),
                obj.disk_policy[mountpoint].get('Major'),
                obj.disk_policy[mountpoint].get('Critical'),
                obj.disk_policy[mountpoint].get('Pass'),
            ) for mountpoint in obj.disk_policy.keys()))
        return result

    disk_vec.short_description = 'Disk 告警(%)'

    def ADD_or_Modify_policy(self, request, queryset):
        if request.POST.get('apply'):
            RE_policyType = request.POST['_policyType']
            RE_policyName = request.POST['_policyName']
            RE_policyValue = request.POST['_policyValue']
            for obj in queryset:
                if "cpu" in RE_policyType:
                    policy = eval(str(obj.cpu_policy))
                    policy[RE_policyName] = int(RE_policyValue)
                    obj.cpu_policy = str(policy)
                    obj.save()
                elif "mem" in RE_policyType:
                    policy = eval(str(obj.cpu_policy))
                    policy[RE_policyName] = int(RE_policyValue)
                    obj.memory_policy = str(policy)
                    obj.save()
                elif "swap" in RE_policyType:
                    policy = eval(str(obj.cpu_policy))
                    policy[RE_policyName] = int(RE_policyValue)
                    obj.swap_policy = str(policy)
                    obj.save()
                # disk
                else:
                    sumPolicy = {}
                    rePolicy = eval(str(obj.disk_policy))
                    for mp, policy in rePolicy.items():
                        policy[RE_policyName] = int(RE_policyValue)
                        sumPolicy[mp] = policy
                    obj.disk_policy = str(sumPolicy)
                    obj.save()
            self.message_user(
                request,
                "{} AM(s) reseted the Policy.".format(queryset.count()))
            return HttpResponseRedirect(request.get_full_path())
        return render(request,
                      'admin/resetpolicy_intermediate.html',
                      context={
                          'qs': queryset,
                      })

    ADD_or_Modify_policy.short_description = "Reset Policy"

    def reset_the_interval(self, request, queryset):
        if request.POST.get('apply'):
            for obj in queryset:
                RE_interval = request.POST['interval_']
                obj.refresh_time_interval = RE_interval
                obj.save()
            self.message_user(
                request, "{} AM(s) reseted the refresh interval.".format(
                    queryset.count()))
            return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            'admin/resetinterval_intermediate.html',
            context={
                'qs': queryset,
                ### default interval
            })

    reset_the_interval.short_description = "Reset Interval"

    # actions = [reset_the_interval, delete_selected]

    def change_group(self, request, queryset):
        if request.POST.get('apply'):
            for obj in queryset:
                RE_group = request.POST['group_']
                try:
                    obj.mygroup_id = MyGroup.objects.get(name=RE_group)
                except:
                    MyGroup.objects.create(name=RE_group)
                    obj.mygroup_id = MyGroup.objects.get(name=RE_group)
                finally:
                    obj.save()
            self.message_user(
                request,
                "{} AM(s) chagned the group.".format(queryset.count()))
            return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            'admin/changegroup_intermediate.html',
            context={
                'qs': queryset,
                ### default interval
            })

    change_group.short_description = "Change Group"

    # queryset.update(mygroup='ungrouped')

    # def export_selected_objects(self, request, queryset):
    #     pass
    #     popup(request)
    #     return popup
    # return render(request, 'popup.html')

    actions = [
        reset_the_interval,
        change_group,
        ADD_or_Modify_policy  # delete_selected,
    ]


admin.site.register(Authenticated_Machine, AM_Admin)

# def admin_popup_test(request):
#     if request.method == "GET":
#         logging.info('get test')
#         return render(request, '/popup.html', {'time_interval': 30})
#     elif request.method == "POST":
#         logging.info('post test')
