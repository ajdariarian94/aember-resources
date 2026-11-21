SUMMARY = "aember package: ConnMan network manager (+ D-Bus)"
DESCRIPTION = "ConnMan (Ethernet, Wi-Fi through wpa_supplicant, DHCP, DNS \
proxy, online check), connmanctl and the D-Bus system bus it talks over, \
for aember devices that run ConnMan instead of aember-netd. Wi-Fi also \
needs the wifi package (wpa_supplicant)."

AEMBER_PACKAGE = "connman"
AEMBER_PACKAGE_INSTALL = "connman connman-client dbus dbus-common dbus-tools"
AEMBER_PACKAGE_USERS = "messagebus"
# Only the system bus: the session-bus tools (dbus-launch links X11) and
# the activation helper (setuid, unused without bus activation) stay out.
AEMBER_PACKAGE_DROP:append = " \
    usr/bin/dbus-launch usr/bin/dbus-run-session \
    usr/bin/dbus-update-activation-environment usr/bin/dbus-cleanup-sockets \
    usr/libexec/dbus-daemon-launch-helper \
    etc/dbus-1/session.conf usr/share/dbus-1/session.conf \
"
# ConnMan's state (saved networks, provisioning files) and D-Bus's.
AEMBER_PACKAGE_DIRS = "/var/lib/connman:0700 /var/lib/dbus:0755"

inherit aember-package
