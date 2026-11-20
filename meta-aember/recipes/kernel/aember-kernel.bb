SUMMARY = "Aember minimal kernel"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-2.0-only;md5=801f80980d171dd6425610833a22dbe6"

DEPENDS += "elfutils-native"

SRC_URI = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.16.tar.xz"
SRC_URI[sha256sum] = "1a4be2fe6b5246aa4ac8987a8a4af34c42a8dd7d08b46ab48516bcc1befbcd83"

# Base config for all architectures
SRC_URI += "file://base.cfg file://trim.cfg"

# Architecture-specific configs
SRC_URI:append:x86-64  = " file://x64-linux.cfg file://trim-x64.cfg"
SRC_URI:append:aarch64 = " file://arm64-linux.cfg file://trim-arm64.cfg"
SRC_URI:append:arm     = " file://arm-linux.cfg file://trim-arm.cfg"
SRC_URI:append:riscv64 = " file://riscv64-linux.cfg file://trim-riscv64.cfg"

KERNEL_DANGLING_FEATURES_WARN_ONLY = "1"

inherit kernel

S = "${UNPACKDIR}/linux-6.16"
STAGING_KERNEL_DIR = "${S}"

FILESEXTRAPATHS:prepend := "${THISDIR}/linux-aember:"

# Architecture-specific default configs
KBUILD_DEFCONFIG:x86-64  = "x86_64_defconfig"
KBUILD_DEFCONFIG:aarch64 = "defconfig"
KBUILD_DEFCONFIG:arm     = "multi_v7_defconfig"
KBUILD_DEFCONFIG:riscv64 = "defconfig"

# Device trees shipped in the kernel asset (dtb/): the Raspberry Pi 4 board
# aember targets, and the Pi 3 one (QEMU's raspi3b can boot it, so the
# Raspberry Pi boot path is testable without hardware).
KERNEL_DEVICETREE:aarch64 = "broadcom/bcm2711-rpi-4-b.dtb broadcom/bcm2837-rpi-3-b.dtb"

# Include modern kbuild module metadata (such as modules.builtin.ranges)
FILES:${KERNEL_PACKAGE_NAME}-modules += "${nonarch_base_libdir}/modules/${KERNEL_VERSION}/modules.builtin*"

# ---------------------------------------------------------------------------
# Aember artifacts go to ${DEPLOYDIR}/aember/<component>/ so they are part of
# do_deploy's sstate: bitbake restores them to
# tmp/deploy/images/${MACHINE}/aember/<component>/ even when the task comes
# from cache. The aember CLI copies them from there to yocto/build/<arch>/.
# Never write outside ${DEPLOYDIR} here; such files are lost on sstate reuse.
# ---------------------------------------------------------------------------
AEMBER_DEPLOY = "${DEPLOYDIR}/aember/kernel"

# ---------------------------------------------------------------------------
# Config fragments. kernel.bbclass (unlike kernel-yocto) does not merge .cfg
# files from SRC_URI, so merge them here with the kernel's merge_config.sh,
# then fail if any requested option did not survive olddefconfig (e.g. an
# unmet dependency), so a fragment can never be silently ignored again.
# ---------------------------------------------------------------------------
AEMBER_KERNEL_FRAGMENTS = "${UNPACKDIR}/base.cfg"
AEMBER_KERNEL_FRAGMENTS:append:x86-64 = " ${UNPACKDIR}/x64-linux.cfg"
AEMBER_KERNEL_FRAGMENTS:append:aarch64 = " ${UNPACKDIR}/arm64-linux.cfg"
AEMBER_KERNEL_FRAGMENTS:append:arm = " ${UNPACKDIR}/arm-linux.cfg"
AEMBER_KERNEL_FRAGMENTS:append:riscv64 = " ${UNPACKDIR}/riscv64-linux.cfg"

# Size trimming (trim*.cfg): merged before the required fragments, so a
# required option always wins over a trim. Best effort: a trimmed option that
# something else still selects only gives a warning (the build stays good,
# just a little bigger), unlike a required option that didn't apply.
AEMBER_KERNEL_TRIM = "${UNPACKDIR}/trim.cfg"
AEMBER_KERNEL_TRIM:append:x86-64 = " ${UNPACKDIR}/trim-x64.cfg"
AEMBER_KERNEL_TRIM:append:aarch64 = " ${UNPACKDIR}/trim-arm64.cfg"
AEMBER_KERNEL_TRIM:append:arm = " ${UNPACKDIR}/trim-arm.cfg"
AEMBER_KERNEL_TRIM:append:riscv64 = " ${UNPACKDIR}/trim-riscv64.cfg"

aember_merge_fragments() {
    ${S}/scripts/kconfig/merge_config.sh -m -O ${B} ${B}/.config ${AEMBER_KERNEL_TRIM} ${AEMBER_KERNEL_FRAGMENTS}
    oe_runmake -C ${S} O=${B} olddefconfig

    kept=""
    for frag in ${AEMBER_KERNEL_TRIM}; do
        for key in $(sed -n 's/^# \(CONFIG_[A-Za-z0-9_]*\) is not set$/\1/p' "$frag"); do
            grep -q "^${key}=" ${B}/.config && kept="$kept $key"
        done
    done
    if [ -n "$kept" ]; then
        bbwarn "Kernel trim options still enabled (selected elsewhere):$kept"
    fi

    missing=""
    for frag in ${AEMBER_KERNEL_FRAGMENTS}; do
        while IFS= read -r line; do
            case "$line" in
                CONFIG_*=n)
                    key=${line%%=*}
                    grep -q "^${key}=" ${B}/.config && missing="$missing $line"
                    ;;
                CONFIG_*=*)
                    grep -qxF "$line" ${B}/.config || missing="$missing $line"
                    ;;
                "# CONFIG_"*" is not set")
                    key=${line#\# }
                    key=${key%% *}
                    grep -q "^${key}=" ${B}/.config && missing="$missing $key=n"
                    ;;
            esac
        done < "$frag"
    done
    if [ -n "$missing" ]; then
        bbfatal "Kernel config fragment options not applied:$missing"
    fi
}

# ---------------------------------------------------------------------------
# Force disable certificates & enforce DRM/VirtIO config
# ---------------------------------------------------------------------------
do_configure:append() {
    aember_merge_fragments

    cat >> ${B}/.config << 'EOF'
CONFIG_VIRTIO_MENU=y
CONFIG_VIRTIO=y
CONFIG_VIRTIO_PCI=y
CONFIG_VIRTIO_MMIO=y
CONFIG_DRM=y
CONFIG_DRM_KMS_HELPER=y
CONFIG_DRM_GEM_SHMEM_HELPER=y
CONFIG_DRM_TTM=y
CONFIG_DRM_TTM_HELPER=y
CONFIG_DRM_VIRTIO_GPU=m
CONFIG_DRM_VIRTIO_GPU_KMS=y
CONFIG_VIRTIO_INPUT=m
EOF

    oe_runmake -C ${S} O=${B} olddefconfig

    sed -i 's/CONFIG_SYSTEM_TRUSTED_KEYS=.*/CONFIG_SYSTEM_TRUSTED_KEYS=""/' ${B}/.config
    sed -i 's/CONFIG_SYSTEM_REVOCATION_KEYS=.*/CONFIG_SYSTEM_REVOCATION_KEYS=""/' ${B}/.config

    cat > ${B}/kernel-build-manifest.txt << MANIFEST
Aember Kernel Build Manifest
============================
Version: ${PV}
Architecture: ${TARGET_ARCH}
Machine: ${MACHINE}
Build Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Compiler: $(${KERNEL_CC} --version 2>/devnull | head -n1 || echo "Unknown")
Defconfig: ${KBUILD_DEFCONFIG}
Kernel Image Type: ${KERNEL_IMAGETYPE}
MANIFEST
}

# ---------------------------------------------------------------------------
# Aember kernel artifact: exactly one image (no versioned/linked copies),
# System.map, Module.symvers, manifest, dtbs and lib/modules/<kver>/.
# ---------------------------------------------------------------------------
do_deploy:append() {
    rm -rf ${AEMBER_DEPLOY}
    install -d ${AEMBER_DEPLOY}

    install -m 0644 ${B}/${KERNEL_OUTPUT_DIR}/${KERNEL_IMAGETYPE} ${AEMBER_DEPLOY}/${KERNEL_IMAGETYPE}
    install -m 0644 ${B}/System.map ${AEMBER_DEPLOY}/
    install -m 0644 ${B}/Module.symvers ${AEMBER_DEPLOY}/
    install -m 0644 ${B}/kernel-build-manifest.txt ${AEMBER_DEPLOY}/

    # kernel-devicetree installs the dtbs flat under KERNEL_DTBDEST
    for dtbf in ${KERNEL_DEVICETREE}; do
        install -Dm 0644 ${D}/${KERNEL_DTBDEST}/$(basename $dtbf) \
            ${AEMBER_DEPLOY}/dtb/$(basename $dtbf)
    done

    if [ -d "${D}${nonarch_base_libdir}/modules" ]; then
        install -d ${AEMBER_DEPLOY}/lib
        cp -r ${D}${nonarch_base_libdir}/modules ${AEMBER_DEPLOY}/lib/
        # Modules aren't signed, so stripping debug info is safe
        find ${AEMBER_DEPLOY}/lib/modules -name '*.ko' -exec ${KERNEL_STRIP} --strip-debug {} +
        # Ship modules.dep & co. so consumers don't run depmod themselves
        # (kernel.bbclass installs with DEPMOD=echo)
        for kdir in ${AEMBER_DEPLOY}/lib/modules/*; do
            depmod -a -b ${AEMBER_DEPLOY} -F ${B}/System.map $(basename $kdir)
            test -s $kdir/modules.dep || bbfatal "depmod produced no modules.dep in $kdir"
        done
    fi
}

INSANE_SKIP += "buildpaths"

COMPATIBLE_MACHINE = "x64-linux|arm64-linux|arm-linux|riscv64-linux"