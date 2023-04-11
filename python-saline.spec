# spec file for package python-saline

%{?!python_module:%define python_module() python3-%{**}}

Name:           python-saline
Version:        2023.04.11
Release:        0
Summary:        The salt event collector and manager
License:        GPL-2.0+
Group:          System/Management
URL:            https://github.com/vzhestkov/saline
Source0:        saline-2023.04.11.tar.gz
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
Saline is an extension for Salt gathering the metrics from salt events.

%package -n saline
Summary:        The salt event collector and manager
Requires(pre):  salt
Requires:       logrotate
Requires:       salt-master
Requires:       systemd
Requires:       saline(module-python) = %{version}-%{release}

%description -n saline
Saline is an extension for Salt gathering the metrics from salt events.

%prep
%autosetup -n saline-%{version}

%build
%python_build

%install
install -Dpm 0644 salined.service %{buildroot}%{_unitdir}/salined.service

install -Dd -m 0755 %{buildroot}%{_sbindir}
ln -sv %{_sbindir}/service %{buildroot}%{_sbindir}/rcsalined

install -Dpm 0644 uyuni-conf/logrotate.d/saline %{buildroot}%{_sysconfdir}/logrotate.d/saline

install -D -d %{buildroot}%{_sysconfdir}/salt/saline.d

install -Dpm 0644 uyuni-conf/salt/saline %{buildroot}%{_sysconfdir}/salt/saline
install -Dpm 0644 uyuni-conf/salt/saline.d/*.conf %{buildroot}%{_sysconfdir}/salt/saline.d/

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
%{_sbindir}/rcsalined
%{_unitdir}/salined.service
%ghost %dir /var/log/salt
%ghost /var/log/salt/saline
%ghost /var/log/salt/saline-api-access.log
%ghost /var/log/salt/saline-api-error.log

%changelog
