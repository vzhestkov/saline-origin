saline-prometheus-cfg:
  file.managed:
  - name: /etc/prometheus/saline.yml
  - contents: |
      - targets:
        - {{ salt['pillar.get']('mgr_server') }}:8216
        labels:
          __scheme__: https
  - require_in:
    - file: config_file
