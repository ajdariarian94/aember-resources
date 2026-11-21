# aember's "wifi" package only (kas/recipes/wifi.yml sets AEMBER_WIFI = "1"):
# a minimal wpa_supplicant with wolfSSL (aember-wpa_supplicant.config). Any
# other build of wpa-supplicant stays as poky has it.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

AEMBER_WIFI ??= ""

SRC_URI:append = "${@' file://aember-wpa_supplicant.config' if d.getVar('AEMBER_WIFI') == '1' else ''}"
DEPENDS:append = "${@' wolfssl' if d.getVar('AEMBER_WIFI') == '1' else ''}"

do_configure:append () {
    if [ "${AEMBER_WIFI}" = "1" ]; then
        cp ${UNPACKDIR}/aember-wpa_supplicant.config wpa_supplicant/.config
    fi
}
