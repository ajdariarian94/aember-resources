# aember-package: an opt-in package for aember devices (SSH, Wi-Fi, ...).
#
# A package recipe is a tiny image: it sets AEMBER_PACKAGE (the component
# name) and AEMBER_PACKAGE_INSTALL (the Yocto packages), and this class
# deploys their files as one tree,
#
#   ${DEPLOY_DIR_IMAGE}/aember/<AEMBER_PACKAGE>/
#     rootfs/         files as they go into the device's root filesystem
#     packages.txt    the Yocto packages and versions shipped
#     symlinks.txt    "<path> <target>" per symlink (not in rootfs/)
#     dirs.txt        "<path> <octal mode>" per directory the programs need
#                     but nothing ships a file in (AEMBER_PACKAGE_DIRS)
#
# through IMGDEPLOYDIR, which is do_image_complete's sstate output, so the
# tree is restored even when every task comes from cache (like do_deploy for
# the other components). aember copies rootfs/ into a board's image only when
# the board lists the package.
#
# What ships: the files of the AEMBER_PACKAGE_INSTALL packages (from pkgdata,
# minus init scripts and docs) and the shared libraries their ELF files need
# (DT_NEEDED, recursively), except the C library: aember's image has it
# already. Everything else the image pulled in (base-files, shells, the
# update-alternatives tool, ...) is left out. Symlinks to shipped files are
# kept (multi-call binaries, update-alternatives links, library sonames).
# Release zips store links as copies, so they go into symlinks.txt instead
# and aember recreates them.

AEMBER_PACKAGE ?= ""
AEMBER_PACKAGE_INSTALL ?= ""
# Empty directories to create on the device, "<path>:<octal mode>" each
# (zips can't hold them): e.g. Dropbear's host key directory.
AEMBER_PACKAGE_DIRS ?= ""

IMAGE_INSTALL = "${AEMBER_PACKAGE_INSTALL}"
IMAGE_FEATURES = ""
IMAGE_LINGUAS = ""
# Only what the packages depend on, not what they merely recommend.
NO_RECOMMENDATIONS = "1"
LDCONFIGDEPEND = ""
USE_LDCONFIG = "0"

IMAGE_FSTYPES = "aember"
IMAGE_TYPES += "aember"

inherit image

LICENSE = "MIT"
COMPATIBLE_MACHINE = "x64-linux|arm64-linux|arm-linux|riscv64-linux"

AEMBER_PACKAGE_TREE = "${WORKDIR}/aember-package"

# Package files never shipped (path prefixes, relative to the rootfs).
AEMBER_PACKAGE_DROP = " \
    etc/init.d/ etc/rc0.d/ etc/rc1.d/ etc/rc2.d/ etc/rc3.d/ etc/rc4.d/ \
    etc/rc5.d/ etc/rc6.d/ etc/rcS.d/ etc/default/ \
    usr/share/doc/ usr/share/man/ usr/share/info/ usr/share/locale/ \
    usr/lib/systemd/ lib/systemd/ \
"

# The C library (glibc and musl), by soname: aember's image brings it.
AEMBER_PACKAGE_LIBC = " \
    ld-linux* ld-musl-* libc.so libc.so.* libc.musl-* libm.so.* libdl.so.* \
    libpthread.so.* librt.so.* libresolv.so.* libutil.so.* libanl.so.* \
    libmvec.so.* libgcc_s.so.* libstdc++.so.* \
"

def aember_elf_needed(path):
    """DT_NEEDED sonames of an ELF file ([] for anything else)."""
    import struct
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF":
        return []
    is64 = data[4] == 2
    end = "<" if data[5] == 1 else ">"
    if is64:
        shoff, = struct.unpack_from(end + "Q", data, 0x28)
        shentsize, shnum = struct.unpack_from(end + "HH", data, 0x3A)
    else:
        shoff, = struct.unpack_from(end + "I", data, 0x20)
        shentsize, shnum = struct.unpack_from(end + "HH", data, 0x2E)
    sections = []
    for i in range(shnum):
        off = shoff + i * shentsize
        if is64:
            _, stype, _, _, soff, ssize, link = struct.unpack_from(end + "IIQQQQI", data, off)
        else:
            _, stype, _, _, soff, ssize, link = struct.unpack_from(end + "IIIIIII", data, off)
        sections.append((stype, soff, ssize, link))
    needed = []
    for stype, soff, ssize, link in sections:
        if stype != 6:  # SHT_DYNAMIC
            continue
        _, stroff, _, _ = sections[link]
        fmt, step = (end + "qQ", 16) if is64 else (end + "iI", 8)
        for off in range(soff, soff + ssize, step):
            tag, val = struct.unpack_from(fmt, data, off)
            if tag == 0:
                break
            if tag == 1:  # DT_NEEDED
                name = data[stroff + val:data.index(b"\0", stroff + val)]
                needed.append(name.decode())
    return needed

def aember_pkg_files(d, runtime):
    """Files (rootfs-relative) of a runtime package, from pkgdata's
    runtime-reverse map (runtime names like libz1 differ from recipe
    package names like zlib)."""
    import json, os
    path = os.path.join(d.getVar("PKGDATA_DIR"), "runtime-reverse", runtime)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        for line in f:
            key, _, value = line.partition(": ")
            if key.startswith("FILES_INFO:"):
                return [p.lstrip("/") for p in json.loads(value)]
    return []

def aember_resolve(rootfs, rel):
    """Follow symlinks inside rootfs (absolute targets are rootfs-relative).
    Returns the rootfs-relative path of the final file, or None."""
    import os
    path = rel
    for _ in range(20):
        full = os.path.join(rootfs, path)
        if not os.path.islink(full):
            return path if os.path.lexists(full) else None
        target = os.readlink(full)
        if target.startswith("/"):
            path = os.path.normpath(target.lstrip("/"))
        else:
            path = os.path.normpath(os.path.join(os.path.dirname(path), target))
    return None

python aember_package_tree () {
    import fnmatch, os, shutil
    import oe.rootfs

    rootfs = d.getVar("IMAGE_ROOTFS")
    out = d.getVar("AEMBER_PACKAGE_TREE")
    drop = d.getVar("AEMBER_PACKAGE_DROP").split()
    libc = d.getVar("AEMBER_PACKAGE_LIBC").split()
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "rootfs"))

    installed = oe.rootfs.image_list_installed_packages(d)
    requested = d.getVar("AEMBER_PACKAGE_INSTALL").split()
    keep = set()
    shipped = set(requested)
    for pkg in requested:
        if pkg not in installed:
            bb.fatal("aember package: %s is not installed" % pkg)
        for rel in aember_pkg_files(d, pkg):
            if any(rel.startswith(p) for p in drop):
                continue
            if os.path.lexists(os.path.join(rootfs, rel)):
                keep.add(rel)

    # Shared libraries, recursively; every soname must resolve.
    def find_lib(soname):
        for libdir in ("lib", "usr/lib"):
            if os.path.lexists(os.path.join(rootfs, libdir, soname)):
                return os.path.join(libdir, soname)
        return None

    owner = {}
    for pkg in installed:
        for rel in aember_pkg_files(d, pkg):
            owner[rel] = pkg

    todo = [f for f in keep if os.path.isfile(os.path.join(rootfs, f))]
    seen = set()
    while todo:
        rel = todo.pop()
        real = aember_resolve(rootfs, rel)
        if real is None or real in seen or not os.path.isfile(os.path.join(rootfs, real)):
            continue
        seen.add(real)
        for soname in aember_elf_needed(os.path.join(rootfs, real)):
            if any(fnmatch.fnmatch(soname, p) for p in libc):
                continue
            lib = find_lib(soname)
            if lib is None:
                bb.fatal("aember package: %s needs %s, which isn't in the image" % (rel, soname))
            target = aember_resolve(rootfs, lib)
            for path in (lib, target):
                if path not in keep:
                    keep.add(path)
                    todo.append(path)
            shipped.add(owner.get(target, owner.get(lib, "?")))

    # Symlinks anywhere in the image that point at a shipped file
    # (update-alternatives links aren't in any package's file list).
    for dirpath, dirnames, filenames in os.walk(rootfs):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, rootfs)
            if not os.path.islink(path) or any(rel.startswith(p) for p in drop):
                continue
            if aember_resolve(rootfs, rel) in keep:
                keep.add(rel)

    links = []
    inodes = {}
    for rel in sorted(keep):
        src = os.path.join(rootfs, rel)
        if os.path.islink(src):
            links.append("/%s %s" % (rel, os.readlink(src)))
            continue
        if not os.path.isfile(src):
            continue
        # Hard links (e2fsprogs' fsck.ext4 = e2fsck) ship once; the other
        # names become symlinks to the first.
        st = os.stat(src)
        first = inodes.setdefault((st.st_dev, st.st_ino), rel)
        if first != rel:
            links.append("/%s /%s" % (rel, first))
        else:
            dst = os.path.join(out, "rootfs", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            shutil.copymode(src, dst)
    if not any(files for _, _, files in os.walk(os.path.join(out, "rootfs"))):
        bb.fatal("aember package %s: no files to ship" % d.getVar("AEMBER_PACKAGE"))
    with open(os.path.join(out, "symlinks.txt"), "w") as f:
        f.writelines(l + "\n" for l in links)
    with open(os.path.join(out, "dirs.txt"), "w") as f:
        for entry in d.getVar("AEMBER_PACKAGE_DIRS").split():
            path, _, mode = entry.partition(":")
            if not path.startswith("/") or not mode:
                bb.fatal("AEMBER_PACKAGE_DIRS: want <path>:<mode>, got %s" % entry)
            int(mode, 8)
            f.write("%s %s\n" % (path, mode))
    with open(os.path.join(out, "packages.txt"), "w") as f:
        for pkg in sorted(shipped):
            info = installed.get(pkg, {})
            f.write("%s %s %s\n" % (pkg, info.get("arch", "?"), info.get("ver", "?")))
}
ROOTFS_POSTPROCESS_COMMAND += "aember_package_tree"

IMAGE_CMD:aember () {
    out="${IMGDEPLOYDIR}/aember/${AEMBER_PACKAGE}"
    rm -rf "${out}"
    mkdir -p "${out}"
    cp -R --no-preserve=ownership "${AEMBER_PACKAGE_TREE}/." "${out}/"
}

python () {
    if not d.getVar("AEMBER_PACKAGE"):
        bb.fatal("%s: set AEMBER_PACKAGE" % d.getVar("PN"))
    if not d.getVar("AEMBER_PACKAGE_INSTALL"):
        bb.fatal("%s: set AEMBER_PACKAGE_INSTALL" % d.getVar("PN"))
}
