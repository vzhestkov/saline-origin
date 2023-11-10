{%- if salt['pillar.get']('mgr_server_is_uyuni', True) %}
  {% set product_name = 'Uyuni' %}
{%- else %}
  {% set product_name = 'SUSE Manager' %}
{%- endif %}

{%- if salt['pillar.get']('saline_grafana:dashboards:add_uyuni_saline_dashboard', False) %}
/etc/grafana/provisioning/dashboards/mgr-server-and-saline.json:
  file.managed:
    - source: "salt://saline-grafana/files/mgr-server-and-saline.json.jinja"
    - makedirs: True
    - template: jinja
    - defaults:
      product_name: {{ product_name }}
{%- else %}
/etc/grafana/provisioning/dashboards/mgr-server-and-saline.json:
  file.absent
{%- endif %}

{%- if salt['pillar.get']('saline_grafana:dashboards:add_uyuni_saline_state_dashboard', False) %}
/etc/grafana/provisioning/dashboards/mgr-saline-state-jobs.json:
  file.managed:
    - source: "salt://saline-grafana/files/mgr-saline-state-jobs.json.jinja"
    - makedirs: True
    - template: jinja
    - defaults:
      product_name: {{ product_name }}
{%- else %}
/etc/grafana/provisioning/dashboards/mgr-saline-state-jobs.json:
  file.absent
{%- endif %}
