# TODO — aember-resources

Ideas and findings collected so far. **Nothing here is approved yet:** implement
an item only when the user says so. aember-side items are in
`../aember/TODO.md`.

**Agreed order (2026-11-15):** 1. aarch64 working end to end, 2. arm32,
3. then size optimization (kernel trimming etc.).

## Opt-in packages (agreed 2026-11-21)

Prebuilt programs a board can opt in to (aember's
`etc/aember/packages.json`): each is its own component and release asset
(`aember-<pkg>-<arch>-v<V>.zip`), built by a small image recipe
(`meta-aember/classes-recipe/aember-package.bbclass`) that ships only the
programs and the libraries they need beyond the C library. Containers are
not built here (aember-build-helper packs Docker images); time sync is
BusyBox `ntpd` (already in BusyBox). Order:

- [x] **Package infrastructure + Dropbear** (SSH server, ~0.7 MB on glibc,
  0.5 MB on musl). Tested in aember's QEMU x64: public-key login.
- [x] **e2fsprogs**: `e2fsck`, `mke2fs`, `resize2fs`, `tune2fs`/`e2label`
  (1.7 MB on x64 with libext2fs, libblkid, libuuid). Tested in aember's
  QEMU x64: ext4 with journal made, checked, grown, labelled.
- [x] **Wi-Fi**: every kernel has `cfg80211`, `mac80211` and
  `mac80211_hwsim` as modules (arm64 also `brcmfmac` + SDIO for the Pi 4).
  `wifi`: wpa_supplicant (WPA2 + WPA3-SAE, D-Bus, no P2P/WPS/EAP), wpa_cli,
  wpa_passphrase, iw, the signed regulatory database, on aarch64 the Pi 4's
  BCM43455 firmware: 3.5 MB (x64), 4.5 MB (aarch64). `wifi-ap`: hostapd
  (WPA2/WPA3), 2.6 MB. Both use wolfSSL (meta-networking) instead of
  OpenSSL (12 MB and 8.6 MB before). Tested in aember's QEMU x64 with
  `mac80211_hwsim`: WPA3-SAE client joins the AP, DHCP over Wi-Fi, ping.
  Not yet on a real Pi 4.
- [x] **ConnMan + D-Bus** (`connman`, 7.8 MB on x64, mostly GLib): ConnMan
  (Ethernet, Wi-Fi through the `wifi` package's wpa_supplicant, nftables
  firewall, no WISPr/VPN/Bluetooth), connmanctl, the D-Bus system bus
  (`messagebus` user through `users.txt`; no session-bus tools, they link
  X11). nf_tables modules in every kernel. wpa_supplicant now has 802.1X
  (PEAP/TTLS/TLS): without any EAP method its D-Bus property query fails
  and ConnMan never sees the Wi-Fi interface. Tested in aember's QEMU x64:
  ConnMan instead of netd, Ethernet online, joins the hwsim AP from a
  provisioning file (needs `AlwaysConnectedTechnologies = ethernet,wifi`
  while Ethernet is up).
- [ ] **OTA updates (RAUC)**: needs the external meta-rauc layer, an A/B
  root partition layout in aember's Pi/USB images and bootloader slot
  selection; the biggest item.
- [ ] Release all packages for every architecture (v0.1.14).

## Architectures

- [x] **aarch64 (Raspberry Pi 4, Cortex-A72):** kernel, BusyBox, LXC and SDK
  for `aarch64-poky-linux` released in v0.1.2; aember boots them in QEMU.
- [x] **arm32 (ARMv7-A hf NEON, `arm-poky-linux`):** kernel, BusyBox, LXC and
  SDK released in v0.1.3; aember boots them in QEMU (`virt`, Cortex-A15).
  `lxc-checkconfig` is clean on x64, arm64 and arm (only the optional items
  below are missing).
- [ ] arm32 on real boards needs their device trees (`KERNEL_DEVICETREE`) and
  a bootloader story; only QEMU `virt` is tested.
- [x] **riscv64 (RV64GC, `riscv64-poky-linux`, v0.1.8):** kernel, BusyBox,
  LXC and SDK; QEMU `virt`. Real boards (VisionFive 2, Milk-V) need their
  device trees and a boot flow (U-Boot/OpenSBI images).
- [x] **Generic aarch64 (v0.1.8):** the `cortexa53` tune instead of
  `cortexa72`, so one aarch64 build runs on every 64-bit Arm board.
- [ ] Raspberry Pi 5 (BCM2712; RP1 support in the mainline kernel).
- [ ] Pi HDMI console (vc4 DRM) in the arm64 kernel.
- [ ] A debug kernel variant (KASAN, lockdep, kmemleak) for aember's QEMU
  system tests.

## SDK

- [x] **Sanitizer runtimes** (`gcc-sanitizers`) in every SDK (v0.1.8), for
  aember's `aember test --sanitize asan|tsan`.
- [ ] **musl variants (opt-in, glibc stays the default):** done for all
  four (x64 v0.1.9, aarch64 v0.1.10, arm32 v0.1.11, riscv64 v0.1.12). `TCLIBC = "musl"`
  builds of the SDK and LXC as extra architectures (`<arch>-poky-linux-musl`),
  for aember's `-musl` targets (smaller images). Same GCC 15, other libc:
  one more SDK, LXC and CAS key per architecture, so builds and release
  assets double for the archs that get it. No sanitizer runtimes there
  (GCC's sanitizers don't support musl). Start with one arch (aarch64 or
  x64), one at a time, with the gcc memory caps.
- [ ] LXC asset: ship a separate stripped liblxc (or split debug info) so
  every consumer gets the small one; aember strips it in Release images
  (4.8 MB -> 1.1 MB). The lxc-* tools could go too (not used by aember).

- [x] **Qt 6 (minimal qtbase) in every SDK** (v0.1.13) for aember-monitor.
- [ ] Qt input (libinput/evdev) and fontconfig if a UI needs touch or many
  fonts: `PACKAGECONFIG:pn-qtbase` in `kas/recipes/sdk.yml`.

## Kernel

- [x] **QEMU watchdog** (`I6300ESB_WDT`) in every kernel (v0.1.6), for
  aember's watchdog tests.
- [x] **x64 PC hardware** (v0.1.7): UEFI framebuffer, Realtek/Intel NICs,
  NVMe, iTCO/SP5100 watchdogs, for aember's USB stick image. Tested in
  QEMU (OVMF, USB stick, e1000e); not yet on a real PC.
- [ ] x64 Wi-Fi and firmware files (`linux-firmware`: r8169 PHY patches,
  i915 DMC) are not shipped; Realtek NICs mostly work without.
- [x] **Ship `modules.dep`** and the other depmod outputs in the kernel
  asset (v0.1.4); modules are stripped.
- [x] **Smaller kernels** (v0.1.4): `trim.cfg` + `trim-<arch>.cfg` remove
  tracing/debug info and subsystems and platforms aember doesn't use.
- [ ] Trim further: `RPMSG` (and `ARCH_BCM_MOBILE` on arm32) are still
  selected by something; x64 keeps `i915` (provides `DRM_TTM`, needed for
  real Intel boxes). A tinyconfig-based kernel would be smaller still.
- [x] Raspberry Pi 4 device tree and built-in Pi drivers (v0.1.5).
- [ ] Pi 4 HDMI console: `DRM_VC4` (+ its modules) isn't enabled yet.
- [ ] aarch64 ships an uncompressed `Image` (19.5 MB, 8.5 MB gzipped);
  `Image.gz` would need aember's packer and the RPi boot config to follow.
- [ ] Optional LXC features `lxc-checkconfig` still reports missing:
  `IP6_NF_TARGET_MASQUERADE` (IPv6 NAT for containers) and
  checkpoint/restore (`*_DIAG`). Only if needed.

## Build and release tooling

- [ ] Dev container: rebuild the image so `gh` and `pkgconf` (already in the
  Dockerfile) are installed; they were only added by hand to the running
  container.
- [ ] `aember publish`: a stale CDN 404 can briefly hide a fresh asset when
  verifying downloads right after upload; if a verify step is added, retry.
