%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%define __getent   /usr/bin/getent
%define __useradd  /usr/sbin/useradd
%define __userdel  /usr/sbin/userdel
%define __groupadd /usr/sbin/groupadd
%define __touch    /bin/touch
%define __service  /sbin/service

Name:           carbon
Version:        0.9.10
Release:        1.2%{dist}
Summary:        Backend data caching and persistence daemon for Graphite
Group:          Applications/Internet
License:        Apache Software License 2.0
URL:            https://launchpad.net/graphite
Vendor:         Chris Davis <chrismd@gmail.com>
Packager:       Dan Carley <dan.carley@gmail.com>
Source0:        https://github.com/downloads/graphite-project/%{name}/%{name}-%{version}.tar.gz
Patch0:         %{name}-setup.patch
Patch1:         %{name}-config.patch
Source1:        %{name}-cache.init
Source2:        %{name}-cache.sysconfig
Source3:        %{name}-relay.init
Source4:        %{name}-relay.sysconfig
Source5:        %{name}-aggregator.init
Source6:        %{name}-aggregator.sysconfig
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python python-devel python-setuptools
Requires:       python whisper
Requires:       python-twisted-core >= 8.2

%description
The backend for Graphite. Carbon is a data collection and storage agent.  

%prep
%setup -q
%patch0 -p1
%patch1 -p1

%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} -c 'import setuptools; execfile("setup.py")' build

%install
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot}
%{__python} -c 'import setuptools; execfile("setup.py")' install --skip-build --root %{buildroot}

# Create log and var directories
%{__mkdir_p} %{buildroot}%{_localstatedir}/log/%{name}-cache
%{__mkdir_p} %{buildroot}%{_localstatedir}/log/%{name}-relay
%{__mkdir_p} %{buildroot}%{_localstatedir}/log/%{name}-aggregator
%{__mkdir_p} %{buildroot}%{_localstatedir}/lib/%{name}

# Install system configuration and init scripts
%{__install} -Dp -m0755 %{SOURCE1} %{buildroot}%{_initrddir}/%{name}-cache
%{__install} -Dp -m0644 %{SOURCE2} %{buildroot}%{_sysconfdir}/sysconfig/%{name}-cache
%{__install} -Dp -m0755 %{SOURCE3} %{buildroot}%{_initrddir}/%{name}-relay
%{__install} -Dp -m0644 %{SOURCE4} %{buildroot}%{_sysconfdir}/sysconfig/%{name}-relay
%{__install} -Dp -m0755 %{SOURCE5} %{buildroot}%{_initrddir}/%{name}-aggregator
%{__install} -Dp -m0644 %{SOURCE6} %{buildroot}%{_sysconfdir}/sysconfig/%{name}-aggregator

# Install default configuration files
%{__mkdir_p} %{buildroot}%{_sysconfdir}/%{name}
%{__install} -Dp -m0644 conf/carbon.conf.example %{buildroot}%{_sysconfdir}/%{name}/carbon.conf
%{__install} -Dp -m0644 conf/storage-schemas.conf.example %{buildroot}%{_sysconfdir}/%{name}/storage-schemas.conf

# Create transient files in buildroot for ghosting
%{__mkdir_p} %{buildroot}%{_localstatedir}/lock/subsys
%{__touch} %{buildroot}%{_localstatedir}/lock/subsys/%{name}-cache
%{__touch} %{buildroot}%{_localstatedir}/lock/subsys/%{name}-relay
%{__touch} %{buildroot}%{_localstatedir}/lock/subsys/%{name}-aggregator

%{__mkdir_p} %{buildroot}%{_localstatedir}/run
%{__touch} %{buildroot}%{_localstatedir}/run/%{name}-cache.pid
%{__touch} %{buildroot}%{_localstatedir}/run/%{name}-relay.pid
%{__touch} %{buildroot}%{_localstatedir}/run/%{name}-aggregator.pid

%pre
%{__getent} group %{name} >/dev/null || %{__groupadd} -r %{name}
%{__getent} passwd %{name} >/dev/null || \
    %{__useradd} -r -g %{name} -d %{_localstatedir}/lib/%{name} \
    -s /sbin/nologin -c "Carbon cache daemon" %{name}
exit 0

%post
##while this seems a bit overkill, it's to handle the yum upgrade case and preserve running/not running state
for service in %{name}-aggregator %{name}-cache
do
chkconfig --add $service
if [ $1 -gt 1 ]; then
    # restart service if it was running
    if %{__service} $service status > /dev/null 2>&1; then
        echo "Restarting $service service because it was running."
        if ! %{__service} $service restart ; then
                logger -s -t "$service" -- "Installation failure. Not able to restart the service."
                exit 1
        fi
    else
        echo "Starting ${name}"
        if ! %{__service} $service start ; then
                logger -s -t "$service" -- "Installation failure. Not able to start the service."
                exit 1
        fi
    fi
else
#go ahead and start it if we didn't hit the above case - we chkconfig'd it on after all.
        echo "Starting ${name}"
        if ! %{__service} $service start ; then
                logger -s -t "$service" -- "Installation failure. Not able to start the service."
                exit 1
        fi
fi
done

%preun
#final uninstall will stop service now, update keeps service running to remember service state for restart in post
for service in %{name}-aggregator %{name}-cache
do
if [ $1 = 0 ]; then
        %{__service} $service stop
        #do this in pre, not post - it errors if the init.d script has been removed
        chkconfig --del $service
fi
done
exit 0

%postun
if [ $1 = 0 ]; then
  %{__getent} passwd %{name} >/dev/null && \
      %{__userdel} -r %{name} 2>/dev/null
fi
exit 0

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc LICENSE PKG-INFO conf/*

%{python_sitelib}/*
/usr/bin/*
%{_initrddir}/%{name}-cache
%{_initrddir}/%{name}-relay
%{_initrddir}/%{name}-aggregator

%config %{_sysconfdir}/%{name}
%config %{_sysconfdir}/sysconfig/%{name}-cache
%config %{_sysconfdir}/sysconfig/%{name}-relay
%config %{_sysconfdir}/sysconfig/%{name}-aggregator

%attr(-,%name,%name) %{_localstatedir}/lib/%{name}
%attr(-,%name,%name) %{_localstatedir}/log/%{name}-cache
%attr(-,%name,%name) %{_localstatedir}/log/%{name}-relay
%attr(-,%name,%name) %{_localstatedir}/log/%{name}-aggregator

%ghost %{_localstatedir}/lock/subsys/%{name}-cache
%ghost %{_localstatedir}/run/%{name}-cache.pid
%ghost %{_localstatedir}/lock/subsys/%{name}-relay
%ghost %{_localstatedir}/run/%{name}-relay.pid
%ghost %{_localstatedir}/lock/subsys/%{name}-aggregator
%ghost %{_localstatedir}/run/%{name}-aggregator.pid

%changelog
* Fri Nov 30 2012 David Raistrick <keen99@gmail.com) - 0.9.10-1.2
- add chkconfig for services on install/uninstall, add service stop/start and support upgrade
- only doing carbon-cache and carbon-aggregator right now

* Mon Nov 26 2012 David Raistrick <keen99@gmail.com) - 0.9.10-1.1
- enforce twisted => 8.2 as required for carbon...

* Fri Jun 1 2012 Ben P <ben@g.megatron.org> - 0.9.10-1
- New upstream version.

* Fri Feb 17 2012 Justin Burnham <justin@jburnham.net> - 0.9.9-4
- Standardized naming to make things more specific.
- Old carbon init script is now called carbon-cache.
- Adding carbon-relay and carbon-aggregator support.

* Wed Nov 2 2011 Dan Carley <dan.carley@gmail.com> - 0.9.9-3
- Correct python-twisted-core dependency from 0.8 to 8.0

* Mon Oct 17 2011 Dan Carley <dan.carley@gmail.com> - 0.9.9-2
- Fix config for relocated data directories.

* Sat Oct 8 2011 Dan Carley <dan.carley@gmail.com> - 0.9.9-1
- New upstream version.

* Mon May 23 2011 Dan Carley <dan.carley@gmail.com> - 0.9.8-2
- Repackage with minor changes.
- Require later version of python-twisted-core to fix textFromEventDict error.

* Tue Apr 19 2011 Chris Abernethy <cabernet@chrisabernethy.com> - 0.9.8-1
- Update source to upstream v0.9.8
- Minor updates to spec file

* Thu Mar 17 2011 Daniel Aharon <daharon@sazze.com> - 0.9.7-1
- Add dependencies, description, init script and sysconfig file.
