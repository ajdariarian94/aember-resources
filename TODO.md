# TODO — aember-resources

Ideas and findings collected so far. **Nothing here is approved yet:** implement
an item only when the user says so. aember-side items are in
`../aember/TODO.md`.

**Agreed order (2026-11-15):** 1. aarch64 working end to end, 2. arm32,
3. then size optimization (kernel trimming etc.).

## Architectures

- [x] **aarch64 (Raspberry Pi 4, Cortex-A72):** kernel, BusyBox, LXC and SDK
  for `aarch64-poky-linux` released in v0.1.2; aember boots them in QEMU.
- [ ] aarch64: run `lxc-checkconfig` against the arm64 kernel `.config`
  (only the configure check has been run so far).
- [ ] `aember pack` takes a single `-a`; a second one silently replaces the
  first. Accept several architectures.
- [ ] **arm32 (ARMv7, `arm-poky-linux`)** after aarch64: machine conf and
  `kas/machine/` file, kernel and BusyBox fragments (BusyBox already has an
  `arm-linux.cfg` hook), LXC conf, `config/` entries (machine, kernel image
  `zImage`, SDK sysroot), assets in the release. Own branch.

## Kernel

- [ ] **Ship `modules.dep`** (and the other depmod outputs) in the kernel asset.
  aember currently regenerates the dependency list with `depmod -n` while
  packing.
- [ ] **Hardening/size:** `DEBUG_FS` and `KALLSYMS` stay on because the
  defconfig enables tracing (`FTRACE`, `KPROBES`, `BLK_DEV_IO_TRACE`), which
  selects both. Turning them off means disabling tracing in the fragment
  (decide what debugging aember still needs).
- [ ] Consider a smaller base than `x86_64_defconfig` (it has many drivers
  aember never uses); the configure check makes trimming safe.
- [ ] Optional LXC features `lxc-checkconfig` still reports missing:
  `IP6_NF_TARGET_MASQUERADE` (IPv6 NAT for containers) and
  checkpoint/restore (`*_DIAG`). Only if needed.

## Build and release tooling

- [ ] Dev container: rebuild the image so `gh` and `pkgconf` (already in the
  Dockerfile) are installed; they were only added by hand to the running
  container.
- [ ] `gh auth setup-git` in the dev container, so plain `git push` works
  without a one-off credential helper.
- [ ] `aember publish`: a stale CDN 404 can briefly hide a fresh asset when
  verifying downloads right after upload; if a verify step is added, retry.
