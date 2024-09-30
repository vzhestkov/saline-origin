# saline

## Quick start

1. Add saline repository to the Uyuni server:
   ```
   zypper ar https://download.opensuse.org/repositories/home:/vizhestkov:/saline-release/15.5/home:vizhestkov:saline-release.repo
   ```

2. Install saline package to the Uyuni server:
   ```
   zypper in saline
   ```

3. To run the initial configuration the following command can be used:
   ```
   saline-setup run
   ```
   It will ask some questions to configure the service, or you can also run it with `-y` parameter to accept defaults the following way:
   ```
   saline-setup run -y
   ```

4. Prometheus and Grafana can be configured with `Saline Prometheus` and `Saline Grafana` by adding them in the `Monitoring` section of `Formulas -> Configuration` page of the client with Prometheus and Grafana deployed on.

6. The configuration for Prometheus and the dashboards of Grafana will be deployed on applying highstate to the client.

## Grafana Dashboard examples

1. Salt Events:

   ![Salt Events](imgs/salt-events.png)

2. Minions Activity:

   ![Minions Activity](imgs/minions-activity.png)

3. Salt Events by Tags and Functions:

   ![Salt Events by Tags and Functions](imgs/salt-events-by-tags-and-fun.png)

4. Salt States:

   ![Salt States](imgs/salt-states.png)

5. Salt State Jobs:

   ![Salt State Jobs](imgs/salt-state-jobs.png)

5. Salt States Profiling:

   ![Salt State Jobs](imgs/salt-states-profiling.png)
