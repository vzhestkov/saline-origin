# saline

## Quick start

1. Add saline repository to the Uyuni server:
   ```
   zypper ar https://download.opensuse.org/repositories/home:/vzhestkov:/saline/15.4/home:vzhestkov:saline.repo
   ```

2. Install saline package to the Uyuni server:
   ```
   zypper in saline
   ```

3. Enable and start salined service:
   ```
   systemctl enable --now salined.service
   ```
   The service is already preconfigured to work on the Uyuni server

4. Create the salt configuration channel (`Configuration -> Channels -> + Create State Channel`) with the following contents in init.sls:
   ```
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
   ```
   Or copy it from [saline-prometheus-config.sls](https://github.com/vzhestkov/saline/blob/main/prometheus/saline-prometheus-config.sls).

5. Subscribe the Uyuni Proxy server system profile to the salt channel created in previous step (`Configuration -> Manage Configuration Channels -> Subscribe to Channels`).

6. Add `User defined scrape configurations` to the Prometheus formula in the Uyuni Proxy server system profile (`Formulas -> Prometheus -> User defined scrape configurations`):

   Job name: `saline`

   Files: `/etc/prometheus/saline.yml`

7. The Grafana dashboard examples can be taken from [Uyuni-with-Saline.json](https://github.com/vzhestkov/saline/blob/main/grafana/Uyuni-with-Saline.json) and [Saline-State-Jobs.json](https://github.com/vzhestkov/saline/blob/main/grafana/Saline-State-Jobs.json)

## Grafana Dashboard examples

1. Salt Events:

   ![Salt Events](https://github.com/vzhestkov/saline/blob/main/imgs/salt-events.png)

2. Minions Activity:

   ![Minions Activity](https://github.com/vzhestkov/saline/blob/main/imgs/minions-activity.png)

3. Salt Events by Tags and Functions:

   ![Salt Events by Tags and Functions](https://github.com/vzhestkov/saline/blob/main/imgs/salt-events-by-tags-and-fun.png)

4. Salt States:

   ![Salt States](https://github.com/vzhestkov/saline/blob/main/imgs/salt-states.png)

5. Salt State Jobs:

   ![Salt State Jobs](https://github.com/vzhestkov/saline/blob/main/imgs/salt-state-jobs.png)

5. Salt States Profiling:

   ![Salt State Jobs](https://github.com/vzhestkov/saline/blob/main/imgs/salt-states-profiling.png)
