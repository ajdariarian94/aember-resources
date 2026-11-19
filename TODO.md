# TODO — aember-resources

Ideas and findings collected so far. **Nothing here is approved yet:** implement
an item only when the user says so. aember-side items are in
`../aember/TODO.md`.

**Agreed order (2026-11-15):** 1. aarch64 working end to end, 2. arm32,
3. then size optimization (kernel trimming etc.).

## Architectures

- [x] **aarch64 (Raspberry Pi 4, Cortex-A72):** kernel, BusyBox, LXC and SDK
  for `aarch64-poky-linux` released in v0.1.2; aember boots them in QEMU.
- [x] **arm32 (ARMv7-A hf NEON, `arm-poky-linux`):** kernel, BusyBox, LXC and
  SDK released in v0.1.3; aember boots them in QEMU (`virt`, Cortex-A15).
  `lxc-checkconfig` is clean on x64, arm64 and arm (only the optional items
  below are missing).
- [ ] arm32 on real boards needs their device trees (`KERNEL_DEVICETREE`) and
  a bootloader story; only QEMU `virt` is tested.

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
