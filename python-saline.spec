# spec file for package python-saline

%define pythons python3

%{?!python_module:%define python_module() python3-%{**}}

Name:           python-saline
Version:        0
Release:        0
Summary:        The salt events collector and manager python module
License:        GPL-2.0+
Group:          Development/Languages/Python
URL:            https://github.com/vzhestkov/saline
Source0:        saline-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  fdupes
BuildRequires:  python-rpm-macros
BuildRequires:  systemd-rpm-macros
BuildRequires:  %{python_module base}
Requires:       %{python_module salt}
Requires:       config(saline) = %{version}-%{release}
Requires(post): update-alternatives
Requires(postun):update-alternatives
Provides:       saline(module-python) = %{version}-%{release}
BuildRoot:      %{_tmppath}/saline-%{version}
%python_subpackages

%description
Saline python library.

Saline is an extension for Salt providing an extra control of state apply process.
Saline also exposes the metrics from salt events to provide more visible salt monitoring.

%package -n saline
Summary:        The salt events collector and manager
Group:          System/Management
Requires(pre):  salt
Requires:       logrotate
Requires:       salt-master
Requires:       systemd
Requires:       saline(module-python) = %{version}-%{release}
Recommends:     saline-uyuni-config

%description -n saline
Saline is an extension for Salt providing an extra control of state apply process.
Saline also exposes the metrics from salt events to provide more visible salt monitoring.

%package -n saline-uyuni-config
Summary:        The default configuration of Saline for Uyuni and SUSE Manager
Group:          System/Management
Requires:       saline
Requires(pre):  spacewalk-config

%description -n saline-uyuni-config
The default configuration of Saline for Uyuni and SUSE Manager

Saline is an extension for Salt providing an extra control of state apply process.
Saline also exposes the metrics from salt events to provide more visible salt monitoring.

%prep
%autosetup -n saline-%{version}

%build
%python_build

%install
install -Dpm 0644 salined.service %{buildroot}%{_unitdir}/salined.service

install -Dd -m 0755 %{buildroot}%{_sbindir}
ln -sv %{_sbindir}/service %{buildroot}%{_sbindir}/rcsalined

install -Dpm 0644 conf/logrotate.d/saline %{buildroot}%{_sysconfdir}/logrotate.d/saline

install -D -d %{buildroot}%{_sysconfdir}/salt/saline.d

install -Dpm 0644 conf/salt/saline %{buildroot}%{_sysconfdir}/salt/saline
install -Dpm 0644 conf/salt/saline.d/*.conf %{buildroot}%{_sysconfdir}/salt/saline.d/

install -Dpm 0644 uyuni-conf/salt/saline.d/*.conf %{buildroot}%{_sysconfdir}/salt/saline.d/

install -D -d %{buildroot}%{_sysconfdir}/salt/pki/saline

install -d %{buildroot}%{_sysconfdir}/alternatives
%{python_expand %$python_install
mv %{buildroot}%{_bindir}/salined %{buildroot}%{_bindir}/salined-%{$python_bin_suffix}
}
%prepare_alternative salined
%{python_expand \
%fdupes %{buildroot}%{$python_sitelib}
}

%pre -n saline
%service_add_pre salined.service

%preun -n saline
%service_del_preun salined.service

%post
%python_install_alternative salined

%post -n saline
%service_add_post salined.service

%postun
%python_uninstall_alternative salined

%postun -n saline
%service_del_postun_with_restart salined.service

%pre -n saline-uyuni-config
if [ ! -f %{_sysconfdir}/salt/pki/saline/uyuni.crt -a ! -f %{_sysconfdir}/salt/pki/saline/uyuni.key ]; then
    if [ -f %{_sysconfdir}/pki/tls/certs/spacewalk.crt -a -f %{_sysconfdir}/pki/tls/private/spacewalk.key ]; then
        cp %{_sysconfdir}/pki/tls/certs/spacewalk.crt %{_sysconfdir}/salt/pki/saline/uyuni.crt
        cp %{_sysconfdir}/pki/tls/private/spacewalk.key %{_sysconfdir}/salt/pki/saline/uyuni.key
        chown salt:salt %{_sysconfdir}/salt/pki/saline/uyuni.crt %{_sysconfdir}/salt/pki/saline/uyuni.key
        chmod 0644 %{_sysconfdir}/salt/pki/saline/uyuni.crt
        chmod 0600 %{_sysconfdir}/salt/pki/saline/uyuni.key
    fi
fi

%files %python_files
%defattr(-,root,root,-)
%python_alternative %{_bindir}/salined
%{python_sitelib}/saline*

%files -n saline
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/logrotate.d/saline
%dir %{_sysconfdir}/salt/saline.d
%config %{_sysconfdir}/salt/saline
%config %{_sysconfdir}/salt/saline.d/*.conf
%exclude %{_sysconfdir}/salt/saline.d/restapi.conf
%dir %{_sysconfdir}/salt/pki/saline
%{_sbindir}/rcsalined
%{_unitdir}/salined.service
%ghost %dir /var/log/salt
%ghost /var/log/salt/saline

%files -n saline-uyuni-config
%config %{_sysconfdir}/salt/saline.d/restapi.conf
%ghost %config %{_sysconfdir}/salt/pki/saline/uyuni.crt
%ghost %config %{_sysconfdir}/salt/pki/saline/uyuni.key
%ghost /var/log/salt/saline-api-access.log
%ghost /var/log/salt/saline-api-error.log

%changelog
