# TODO — aember-resources

Ideas and findings collected so far. **Nothing here is approved yet:** implement
an item only when the user says so. aember-side items are in
`../aember/TODO.md`.

## Architectures

- [ ] **aarch64 (Raspberry Pi 4, Cortex-A72):** build kernel, BusyBox, LXC and
  SDK for `aarch64-poky-linux`, check the arm64 kernel fragment with the
  configure check and `lxc-checkconfig`, publish the assets. aember's
  `--arch aarch64-poky-linux` builds stop at `FetchResources` until then.

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
