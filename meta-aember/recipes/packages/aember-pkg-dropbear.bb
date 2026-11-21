SUMMARY = "aember package: Dropbear SSH server"
DESCRIPTION = "Dropbear (SSH server, dropbearkey, scp) for aember devices, \
deployed as an opt-in package tree (aember-package.bbclass)."

AEMBER_PACKAGE = "dropbear"
AEMBER_PACKAGE_INSTALL = "dropbear"
# Host keys: `dropbear -R` creates them on the first connection, but not
# their directory.
AEMBER_PACKAGE_DIRS = "/etc/dropbear:0700"

inherit aember-package
