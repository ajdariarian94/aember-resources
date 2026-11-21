# aember's "wifi-ap" package only (kas/recipes/wifi-ap.yml sets
# AEMBER_WIFI = "1"): a minimal hostapd with wolfSSL.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

AEMBER_WIFI ??= ""

SRC_URI:append = "${@' file://aember-hostapd.config' if d.getVar('AEMBER_WIFI') == '1' else ''}"
DEPENDS:remove = "${@'openssl' if d.getVar('AEMBER_WIFI') == '1' else ''}"
DEPENDS:append = "${@' wolfssl' if d.getVar('AEMBER_WIFI') == '1' else ''}"

do_configure:append () {
    if [ "${AEMBER_WIFI}" = "1" ]; then
        install -m 0644 ${UNPACKDIR}/aember-hostapd.config ${B}/hostapd/.config
    fi
}
