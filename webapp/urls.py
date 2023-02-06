from django.urls import re_path
from . import ajax, json, views

urlpatterns = [
    
    re_path(r'^css/(?P<file>.*)$', views.css, name='css'),

    re_path(r'^architecture/(?P<arch_id>[0-9]+)/$', views.architecture, name='architecture'),
    re_path(r'^architecture/(?P<arch_id>[0-9]+)/mapping/$', views.architecture_mapping, name='architecture_mapping'),
    re_path(r'^architecture/(?P<arch_id>[0-9]+)/faults/$', views.architecture_faults, name='architecture_faults'),
    
    re_path(r'^instruction/(?P<instruction_id>[0-9]+)/detail/$', views.detail, name='detail'),
    re_path(r'^instruction/(?P<instruction_id>[0-9]+)/bitflip/$', views.interactive, name='interactive'),

    re_path(r'^softwarelist/(?P<softwarelist_id>[0-9]+)/$', views.softwarelist, name='softwarelist'),
    re_path(r'^software/(?P<software_id>[0-9]+)/$', views.software, name='software'),

    re_path(r'^mutantlist/(?P<mutantlist_id>[0-9]+)/$', views.mutantlist, name='mutantlist'),
    
    re_path(r'^ajax/faulteffect/(?P<instruction_id>[0-9]+)/(?P<fault_mask>[0-9]+)/$', ajax.fault_effect,
            name='ajax_faulteffect'),
    
    re_path(r'^json/encoding/(?P<instruction_id>[0-9]+)/$', json.encoding, name='json_encoding'),
    re_path(r'^json/encoding/(?P<instruction_id>[0-9]+)/(?P<fault_mask>[0-9]+)/$', json.encoding, name='json_encoding'),
    re_path(r'^json/testrelevance/(?P<arch_id>[0-9]+)/(?P<bits>[0-9]+)/$', json.testrelevance, name='testrelevance'),
    re_path(r'^json/faultdistribution/(?P<arch_id>[0-9]+)/$', json.faultdistribution, name='faultdistribution'),
    re_path(r'^json/chartdata/(?P<instruction_id>[0-9]+)/(?P<distance>[0-9]+)/$', json.chartdata, name='chartdata'),
]
