#!/bin/bash

if [ ! -f %{_sysconfdir}/salt/pki/saline/uyuni.crt -a ! -f %{_sysconfdir}/salt/pki/saline/uyuni.key ]; then
    if [ -f %{_sysconfdir}/pki/tls/certs/spacewalk.crt -a -f %{_sysconfdir}/pki/tls/private/spacewalk.key ]; then
        cp %{_sysconfdir}/pki/tls/certs/spacewalk.crt %{_sysconfdir}/salt/pki/saline/uyuni.crt
        cp %{_sysconfdir}/pki/tls/private/spacewalk.key %{_sysconfdir}/salt/pki/saline/uyuni.key
        chown salt:salt %{_sysconfdir}/salt/pki/saline/uyuni.crt %{_sysconfdir}/salt/pki/saline/uyuni.key
        chmod 0644 %{_sysconfdir}/salt/pki/saline/uyuni.crt
        chmod 0600 %{_sysconfdir}/salt/pki/saline/uyuni.key
    fi
fi
