SUMMARY = "aember package: Wi-Fi access point (hostapd)"
DESCRIPTION = "hostapd for aember devices: run a Wi-Fi network (setup \
hotspot, local access point). BusyBox's udhcpd hands out addresses. Also \
used to test the wifi package in QEMU with mac80211_hwsim."

AEMBER_PACKAGE = "wifi-ap"
AEMBER_PACKAGE_INSTALL = "hostapd"
# The 140 KB sample config: a board brings its own hostapd.conf.
AEMBER_PACKAGE_DROP:append = " etc/hostapd.conf"

inherit aember-package
