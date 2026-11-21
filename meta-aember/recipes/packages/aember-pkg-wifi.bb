SUMMARY = "aember package: Wi-Fi client (wpa_supplicant, iw, regulatory database)"
DESCRIPTION = "wpa_supplicant (WPA2/WPA3), wpa_cli, wpa_passphrase, iw and \
the signed wireless regulatory database for aember devices. On aarch64 also \
the Raspberry Pi 4's BCM43455 firmware. The kernel's 802.11 modules \
(cfg80211, mac80211, brcmfmac) come with the kernel asset; a board lists \
them in modules.json."

AEMBER_PACKAGE = "wifi"
AEMBER_PACKAGE_INSTALL = " \
    wpa-supplicant wpa-supplicant-cli wpa-supplicant-passphrase iw \
    wireless-regdb-static \
"
AEMBER_PACKAGE_INSTALL:append:aarch64 = " linux-firmware-bcm43455"

inherit aember-package
