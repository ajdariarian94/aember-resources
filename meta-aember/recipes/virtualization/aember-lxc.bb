SUMMARY = "Aember LXC container runtime"
LICENSE = "LGPL-2.1-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=4b6551da9cb7d5b3017d1c0a3e31469b"

DEPENDS = "glib-2.0 util-linux libcap"

SRC_URI = "https://linuxcontainers.org/downloads/lxc/lxc-6.0.2.tar.gz"
SRC_URI[sha256sum] = "1930aa10d892db8531d1353d15f7ebf5913e74a19e134423e4d074c07f2d6e8b"

SRC_URI += " \
    file://base.conf \
    file://x64-linux.conf \
    file://arm64-linux.conf \
    file://arm-linux.conf \
    file://riscv64-linux.conf \
    file://0001-lxccontainer-prctl-fallback.patch \
"

inherit meson pkgconfig deploy

addtask deploy after do_install before do_build

S = "${UNPACKDIR}/lxc-6.0.2"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Minimal build — no apparmor, selinux, seccomp, openssl, no init scripts.
# Every optional feature is set explicitly: meson would otherwise enable it
# whenever the library happens to be in the sysroot.
EXTRA_OEMESON = " \
    -Dinit-script=[] \
    -Dinstall-state-dirs=false \
    -Dapparmor=false \
    -Dselinux=false \
    -Dseccomp=false \
    -Dcapabilities=false \
    -Dexamples=false \
    -Dman=false \
    -Dlog-path=/var/log/lxc \
    -Ddata-path=/var/lib/lxc \
    -Ddbus=false \
    -Dopenssl=false \
"

do_install:append() {
    install -d ${D}${sysconfdir}/lxc
    install -m 0644 ${WORKDIR}/sources/base.conf ${D}${sysconfdir}/lxc/default.conf

    # Install architecture-specific LXC config
    if [ "${TARGET_ARCH}" = "x86_64" ]; then
        install -m 0644 ${WORKDIR}/sources/x64-linux.conf ${D}${sysconfdir}/lxc/arch.conf
    elif [ "${TARGET_ARCH}" = "aarch64" ]; then
        install -m 0644 ${WORKDIR}/sources/arm64-linux.conf ${D}${sysconfdir}/lxc/arch.conf
    elif [ "${TARGET_ARCH}" = "arm" ]; then
        install -m 0644 ${WORKDIR}/sources/arm-linux.conf ${D}${sysconfdir}/lxc/arch.conf
    elif [ "${TARGET_ARCH}" = "riscv64" ]; then
        install -m 0644 ${WORKDIR}/sources/riscv64-linux.conf ${D}${sysconfdir}/lxc/arch.conf
    fi

    install -d ${D}${localstatedir}/lib/lxc

    # Aember links liblxc dynamically. The static archive embeds build paths
    # (fails the buildpaths QA check) and is never deployed, so drop it.
    rm -f ${D}${libdir}/liblxc.a
}

# Split templates into their own package. ${PN}-dev is already in the default
# PACKAGES list; adding it again fails the packages-list QA check.
PACKAGES =+ "${PN}-templates"

FILES:${PN} = " \
    ${bindir}/lxc-* \
    ${sbindir}/init.lxc \
    ${libdir}/liblxc.so* \
    ${libdir}/lxc/ \
    ${libexecdir}/lxc/ \
    ${sysconfdir}/lxc/ \
    ${sysconfdir}/default/lxc \
    ${localstatedir}/lib/lxc \
    ${datadir}/lxc/ \
    ${datadir}/bash-completion/ \
"

FILES:${PN}-templates = " \
    ${datadir}/lxc/templates/ \
"

# Dev package: headers, pkgconfig, and the unversioned .so linker symlink
FILES:${PN}-dev = " \
    ${includedir}/lxc/ \
    ${libdir}/pkgconfig/lxc.pc \
    ${libdir}/liblxc.so \
"

# Make the dev package depend on the runtime so consumers get everything
RDEPENDS:${PN}-dev = "${PN}"

# Allow the dev package to be built into the SDK / sysroot
ALLOW_EMPTY:${PN}-dev = "1"

# ---------------------------------------------------------------------------
# Aember artifacts go to ${DEPLOYDIR}/aember/<component>/ so they are part of
# do_deploy's sstate: bitbake restores them to
# tmp/deploy/images/${MACHINE}/aember/<component>/ even when the task comes
# from cache. The aember CLI copies them from there to yocto/build/<arch>/.
# Never write outside ${DEPLOYDIR} here; such files are lost on sstate reuse.
# ---------------------------------------------------------------------------
AEMBER_DEPLOY = "${DEPLOYDIR}/aember/lxc"

do_deploy() {
    # Start clean so `cp -r` below never nests etc-lxc/lxc/ on re-runs.
    rm -rf ${AEMBER_DEPLOY}
    install -d ${AEMBER_DEPLOY}

    # ── Runtime binaries ──────────────────────────────────────────────────────
    for bin in ${D}${bindir}/lxc-*; do
        [ -f "$bin" ] && install -m 0755 "$bin" ${AEMBER_DEPLOY}/
    done

    # ── Shared libraries → under libs/ ───────────────────────────────────────
    install -d ${AEMBER_DEPLOY}/libs
    for lib in ${D}${libdir}/liblxc.so*; do
        if [ -L "$lib" ]; then
            cp -P "$lib" ${AEMBER_DEPLOY}/libs/
        elif [ -f "$lib" ]; then
            install -m 0755 "$lib" ${AEMBER_DEPLOY}/libs/
        fi
    done

    # ── Headers ───────────────────────────────────────────────────────────────
    if [ -d "${D}${includedir}/lxc" ]; then
        install -d ${AEMBER_DEPLOY}/include/lxc
        cp -r ${D}${includedir}/lxc/. ${AEMBER_DEPLOY}/include/lxc/
    fi

    # ── pkg-config — relative to the .pc file so the artifact is relocatable ─
    if [ -f "${D}${libdir}/pkgconfig/lxc.pc" ]; then
        install -d ${AEMBER_DEPLOY}/pkgconfig
        # "$D_" is a literal '$': bitbake would expand ${prefix} to /usr itself
        D_='$'
        sed \
            -e "s|^prefix=.*|prefix=${D_}{pcfiledir}/..|" \
            -e "s|^libdir=.*|libdir=${D_}{prefix}/libs|" \
            -e "s|^includedir=.*|includedir=${D_}{prefix}/include|" \
            ${D}${libdir}/pkgconfig/lxc.pc > ${AEMBER_DEPLOY}/pkgconfig/lxc.pc
    fi

    # ── Configs ───────────────────────────────────────────────────────────────
    cp -r ${D}${sysconfdir}/lxc ${AEMBER_DEPLOY}/etc-lxc
}

# Skip buildpaths QA — same as kernel recipe
INSANE_SKIP:${PN} += "buildpaths file-rdeps"
INSANE_SKIP:${PN}-templates += "file-rdeps"
INSANE_SKIP:${PN}-dev += "buildpaths"

COMPATIBLE_MACHINE = "x64-linux|arm64-linux|arm-linux|riscv64-linux"