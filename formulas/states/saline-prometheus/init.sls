{%- if salt['pillar.get']('prometheus:saline_enabled', False) %}
saline-prometheus-cfg:
  file.managed:
  - name: /etc/prometheus/saline.yml
  - contents: |
      - targets:
        - {{ salt['pillar.get']('mgr_server') }}:{{ salt['pillar.get']('prometheus:saline_port') }}
{%- if salt['pillar.get']('prometheus:saline_https_connection', False) %}
        labels:
          __scheme__: https
{% endif %}
  - require_in:
    - file: config_file
{%- endif %}
