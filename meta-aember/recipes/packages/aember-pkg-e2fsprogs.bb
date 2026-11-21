SUMMARY = "aember package: ext4 tools (e2fsck, mke2fs, resize2fs, tune2fs)"
DESCRIPTION = "e2fsprogs' ext2/3/4 tools for aember devices: check, create, \
grow and label file systems (e.g. a data partition at boot). BusyBox's \
mke2fs can't make ext4 with a journal, and BusyBox has no e2fsck or \
resize2fs."

AEMBER_PACKAGE = "e2fsprogs"
AEMBER_PACKAGE_INSTALL = " \
    e2fsprogs-e2fsck e2fsprogs-mke2fs e2fsprogs-resize2fs e2fsprogs-tune2fs \
"

inherit aember-package
