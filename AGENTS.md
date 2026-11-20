# AGENTS.md

Guidance for AI coding agents (Claude Code, Copilot, Codex, …) working in
**aember-resources**.

## What this repo is

`aember-resources` holds the **[kas](https://kas.readthedocs.io/) YAML files
and the Yocto layer (`meta-aember`)** that build the low-level pieces of
Aember, a lightweight embedded-Linux system. It also holds the `aember` CLI,
which runs those builds, hashes them, publishes the results and fetches them
again:

- Linux kernel
- BusyBox
- LXC
- SDK / compilers (Poky SDK toolchain: GCC 15, C++23, no custom GCC)

kas files say **which layers (external ones pinned by commit), which machine,
which local.conf settings and which bitbake target** to use. The recipes live
in `meta-aember/` in this repo, and the only external layer is Poky.

### meta-aember (in this repo)

| What           | Path                                                                  |
|----------------|-----------------------------------------------------------------------|
| Layer config   | `meta-aember/conf/layer.conf` (`LAYERSERIES_COMPAT = "whinlatter"`)   |
| Machines       | `meta-aember/conf/machine/{x64-linux,arm64-linux,arm-linux,riscv64-linux}.conf` |
| Kernel         | `meta-aember/recipes/kernel/aember-kernel.bb` (linux 6.16, `files/{base,x64-linux,arm64-linux,arm-linux,riscv64-linux}.cfg`) |
| BusyBox        | `meta-aember/recipes/busybox/aember-busybox.bb` (1.36.1, static, `.cfg` fragments) |
| LXC            | `meta-aember/recipes/virtualization/aember-lxc.bb` (6.0.2, meson, prctl patch, `.conf` files) |
| Poky           | cloned by kas into `yocto/poky` from `https://github.com/ajdariarian94/poky.git`, pinned in `kas/base.yml` |

`kas/base.yml` adds the layer through a repo entry without a `url`, which
kas treats as "the repo this kas file lives in". The layer was copied from
`../aember/yocto/meta-aember` (aember commit `c4aef15`). From now on this
repo's copy is the source of truth, so don't edit or sync from `../aember`.

Recipe rules:
- A recipe's artifact goes **only** into `${DEPLOYDIR}/aember/<component>/`
  (`AEMBER_DEPLOY`) from `do_deploy`, starting with `rm -rf ${AEMBER_DEPLOY}`.
  Never write outside `${DEPLOYDIR}` (no `${TOPDIR}/..`, no absolute paths).
  Only `DEPLOYDIR` is in do_deploy's sstate. A file written anywhere else
  silently goes missing when the task is restored from cache.
- Deploy exactly what consumers need. No versioned image copies or
  symlinks, no static archives. Make text files with paths (`.pc` and so on)
  relocatable (`${pcfiledir}`). Escape `$` (`D_='$'`) wherever bitbake would
  otherwise expand a `${var}` itself.
- Kernel config: the recipe inherits plain `kernel`, which does **not**
  merge `.cfg` files from `SRC_URI` (only `kernel-yocto` does).
  `aember_merge_fragments` in `aember-kernel.bb` merges
  `base.cfg` + `<arch>.cfg` with `scripts/kconfig/merge_config.sh`, runs
  `olddefconfig`, and fails `do_configure` if any fragment line didn't make
  it into `.config` (unknown symbol, unmet dependency, or forced by a
  `select`). Write string options as `CONFIG_X=""`, not `# ... is not set`.
  Check a fragment change quickly with
  `aember kas-shell kernel -c "bitbake -c configure -f aember-kernel"`.
  aember's `modules.json` must only list modules that exist as `.ko` or in
  `modules.builtin`.
- Kernel size: `trim.cfg` + `trim-<arch>.cfg` turn off what appliances
  don't use (sound, Wi-Fi/BT, media, staging, network filesystems, KVM,
  tracing, debug info, unused NIC vendors, and on ARM every SoC platform
  except QEMU virt, Raspberry Pi (BCM2835) and, on arm32, i.MX and STM32).
  They are merged **before** the required fragments (a required option
  always wins) and are best effort: an option something else still selects
  only gives a `bbwarn`, not a failure. Needing a trimmed driver back
  (another board, a NIC): add it to the arch's required fragment.
- aarch64 ships device trees in `kernel/dtb/` (`KERNEL_DEVICETREE:aarch64`:
  Raspberry Pi 4 `bcm2711-rpi-4-b.dtb`, and Pi 3 `bcm2837-rpi-3-b.dtb` for
  aember's QEMU raspi3b test). What the Pi needs before the root switch
  (aember loads modules only afterwards) is built in by `arm64-linux.cfg`:
  firmware/mailbox/clocks (`CLK_RASPBERRYPI`), SD (`MMC_SDHCI_IPROC`,
  `MMC_BCM2835`), the mini UART, plus Ethernet (`BCMGENET`), USB
  (`PCIE_BRCMSTB`), thermal, cpufreq, watchdog.
- The kernel asset ships stripped modules (`--strip-debug`, modules aren't
  signed) and the depmod output (`modules.dep`, `modules.alias`, ...),
  generated in `do_deploy`; aember reads `modules.dep` from it.
- Watchdog: `base.cfg` builds in the watchdog core and `I6300ESB_WDT`
  (QEMU's PCI watchdog, `-device i6300esb`), so aember's watchdog,
  reset included, is testable in QEMU on every architecture (v0.1.6).
- x64 PC hardware (v0.1.7, for aember's bootable USB stick image):
  `x64-linux.cfg` builds in the UEFI framebuffer (`FB_EFI`: screen
  console and `/dev/fb0` on any GPU the firmware set up, also AMD/NVIDIA
  and QEMU's VGA, which have no DRM driver here), Realtek (`R8169`) and
  Intel (`IGB`, `IGC`, besides e1000/e1000e) NICs, NVMe, and the chipset
  watchdogs `ITCO_WDT` (+ `LPC_ICH`) and `SP5100_TCO`.
  `NET_VENDOR_REALTEK` is no longer trimmed on x64. The x86_64 defconfig
  already has the EFI stub, xHCI/EHCI, USB storage, AHCI and USB HID.
- The kernel must run aember's LXC containers (cgroup2): `base.cfg` enables
  squashfs (zstd), overlayfs, the memory controller, BPF device control
  (`BPF_SYSCALL`, `CGROUP_BPF`), veth/bridge, tun, fuse, macvlan, vlan.
  After a config change, check it with LXC's own script:
  `CONFIG=yocto/bitbake/tmp/work/<machine>-poky-linux/aember-kernel/1.0/build/.config sh yocto/build/<arch>/virtualization/lxc-checkconfig`
  (the namespace-limit and cgroup-mount lines describe the host, ignore them).
- Pin sources with `SRC_URI[sha256sum]` (or `SRCREV`). No `AUTOREV`.
- Don't add `${PN}-dev`, `${PN}-dbg` and the like to `PACKAGES` yourself, because
  they're already defaults, and a duplicate fails the `packages-list` QA check.

## Architectures

| Arch key (`ctx.architecture`) | kas/Yocto `machine` | Tune        | Kernel image | Artifact dir                  |
|-------------------------------|---------------------|-------------|--------------|-------------------------------|
| `x64-poky-linux`              | `x64-linux`         | `core2-64`  | `bzImage`    | `yocto/build/x64-poky-linux/` |
| `aarch64-poky-linux`          | `arm64-linux`       | `cortexa53` | `Image`      | `yocto/build/aarch64-poky-linux/` |
| `arm-poky-linux`              | `arm-linux`         | `armv7athf-neon` | `zImage` | `yocto/build/arm-poky-linux/` |
| `riscv64-poky-linux`          | `riscv64-linux`     | `riscv64`   | `Image`      | `yocto/build/riscv64-poky-linux/` |
| `x64-poky-linux-musl`         | `x64-linux` + musl  | `core2-64`  | `bzImage`    | `yocto/build/x64-poky-linux-musl/` |
| `aarch64-poky-linux-musl`     | `arm64-linux` + musl | `cortexa53` | `Image`     | `yocto/build/aarch64-poky-linux-musl/` |
| `arm-poky-linux-musl`         | `arm-linux` + musl  | `armv7athf-neon` | `zImage` | `yocto/build/arm-poky-linux-musl/` (sysroot `armv7at2hf-neon-poky-linux-musleabi`, prefix `arm-poky-linux-musleabi-`) |
| `riscv64-poky-linux-musl`     | `riscv64-linux` + musl | `riscv64` | `Image`     | `yocto/build/riscv64-poky-linux-musl/` (sysroot `riscv64imafdc-poky-linux-musl`) |

aarch64 is generic ARMv8.0-A (`cortexa53` tune since v0.1.8; it was
`cortexa72`, the Pi 4 only): one build for every 64-bit Arm board, the Pi 4
included (A53 code runs on the A72). The SDK's target sysroot is
`cortexa53-poky-linux`.

riscv64 (v0.1.8) is RV64GC, the baseline Linux distributions use: the
`riscv` defconfig (QEMU `virt`, SiFive, StarFive) plus `riscv64-linux.cfg`
(16550 console `ttyS0`, containers, virtio/PCIe, e1000e) and
`trim-riscv64.cfg`. QEMU: `-machine virt` with its built-in OpenSBI
(`-bios default`). `riscv64-linux.cfg` enables the trusted keyring because
`base.cfg` empties `SYSTEM_TRUSTED_KEYS`, which needs it; the riscv
defconfig has no module signing. Validate a fragment before a build:
`make ARCH=riscv defconfig`, `scripts/kconfig/merge_config.sh` with the
trims and fragments, `olddefconfig`, then check each option survived (the
recipe's `aember_merge_fragments` fails the build otherwise, but only after
the cross compiler is built).

**musl variants (v0.1.9, opt-in):** `<arch>-musl` keys (`LIBC_MAP` in
`config/components.py`) use the same MACHINE plus `kas/libc/musl.yml` in
their chain: `TCLIBC = "musl"`, their own `TMPDIR` (`yocto/bitbake/tmp-musl`,
`tmp_dir()`), no `gcc-sanitizers` (GCC's sanitizers don't support musl), and
GCC's make jobs capped at 2 like riscv64. Nothing from the glibc builds is
reused (cross GCC, every target package), so a musl architecture is a full
build. glibc stays the default. Every architecture has one: x64 (v0.1.9), aarch64 (v0.1.10), arm32 (v0.1.11), riscv64 (v0.1.12). The SDK
installer is picked by `poky-<libc>-*-<machine>-toolchain-*.sh`.

arm32 is generic ARMv7-A, hard-float, NEON (Thumb-2 packages:
`armv7at2hf-neon`, toolchain prefix `arm-poky-linux-gnueabi-`), so one build
runs on Cortex-A7/A9/A15 boards. The kernel is `multi_v7_defconfig` without
LPAE; that defconfig lacks namespaces and most cgroup controllers, which
`arm-linux.cfg` adds back (check with `lxc-checkconfig`).

Recipes deploy into `yocto/bitbake/tmp/deploy/images/<machine>/aember/<deploy_name>/`.
That folder is restored from sstate, so it's always current, even when every
task comes from cache. After each kas build, `KasBuild._collect` replaces
`yocto/build/<arch>/<output_dir>/` with a copy of it. The mapping lives in
`COMPONENTS` (`config/components.py`): kernel→`kernel`, busybox→`busybox`,
lxc→`virtualization`. The SDK is the exception: its installer is run into
`yocto/build/<arch>/sdk/`.


## kas files

```
kas/
  base.yml                 # header v23, distro poky, pinned poky + local meta-aember, shared local.conf
  machine/
    x64-linux.yml          # machine: x64-linux
    arm64-linux.yml
    arm-linux.yml
    riscv64-linux.yml
  libc/
    musl.yml               # TCLIBC = musl, own TMPDIR (the <arch>-musl variants)
  recipes/
    kernel.yml             # target: aember-kernel
    busybox.yml            # target: aember-busybox
    lxc.yml                # target: aember-lxc
    sdk.yml                # target: core-image-minimal, task: populate_sdk
```

A component build is always the chain `base.yml:machine/<m>.yml:recipes/<c>.yml`,
with `libc/musl.yml` before the recipe for a musl variant
(`aember/config/components.py::kas_chain`).

### The build host is the kas container

**Every kas/bitbake run happens inside the pinned kas image**
(`KAS_IMAGE` in `config/components.py`: `ghcr.io/siemens/kas/kas:5.4@sha256:…`,
Debian 13). Never run bitbake directly in the dev container: Ubuntu 26.04
(glibc 2.43, GCC 15 defaulting to C23) breaks Poky's host tools (m4's gnulib)
and disables uninative.

`utils/kas_container.py` does what the `kas-container` script does, but it
works from inside the dev container. It talks to the host Docker daemon over
the mounted socket, so the bind mount uses `HOST_ROOT_PATH` (the host path of
the repo, set by devcontainer.json), not `/aember_ws/...`:

```
docker run --rm --user=root -v $HOST_ROOT_PATH:/work -w /work \
  -e USER_ID=<uid> -e GROUP_ID=<gid> \
  -e KAS_WORK_DIR=/work/yocto -e KAS_BUILD_DIR=/work/yocto/bitbake \
  <KAS_IMAGE> <kas command> <chain>
```

`--user=root` is required: the entrypoint remaps `builder` to your uid/gid
and then drops privileges. Don't use the upstream `kas-container` script from
the dev container, because its mounts would resolve to the wrong host paths.

```bash
aember kas-shell kernel -a x64-poky-linux                      # interactive bitbake shell
aember kas-shell busybox -c "bitbake -e aember-busybox | grep ^AEMBER_DEPLOY="
```

Bitbake paths inside the container are `/work/...`. A `yocto/bitbake/` created
by any other host or path has to be deleted (`downloads/` can be kept).
The local `kas` pip package is only for quick `kas dump` checks.

kas rules:

- kas 5.4 (image and `requirements.txt` pin) uses config format **23**.
  Every file starts with `header: version: 23`. Bump the image digest, the pip
  pin and the header version together.
- **Pin every repo to an exact `commit:`.** The `branch:` next to it is
  checked by kas but is only informational. Since there are no floating refs,
  no lock file is needed.
- meta-aember is local (repo entry `aember-resources` with no `url`). Its
  files go into the CAS key directly (`LOCAL_LAYERS` in `config/components.py`).
  **Editing any file in `meta-aember/` or bumping the poky commit changes the
  CAS key of every component.** That's intended, and sstate keeps rebuilds of
  unchanged recipes fast.
- local.conf additions go in `local_conf_header:` blocks with descriptive keys
  and a comment saying *why*. Never hand-edit `yocto/bitbake/conf/`, because
  kas regenerates it.
- `machine` lives only in `machine/*.yml`, and `target`/`task` only in
  `recipes/*.yml`, so any combination composes.
- A new component needs a `kas/recipes/<name>.yml`, an entry in
  `COMPONENTS` (`aember/config/components.py`), and an `is_present` check in
  `steps/kas/build.py`.

## The CAS model

The CAS key of an artifact is the **sha256 of the kas image reference, its
ordered kas chain and every file in `meta-aember/`** (path + content,
`utils/kas_hash.py`). Poky is pinned by commit and the image by digest, so the
key covers the recipes, config fragments, patches and the build host. Nothing is rebuilt
unless the key changes.

```
image + kas chain + meta-aember ──sha256──► key
                       ├─ yocto/build/<arch>/<component>/.kas-hash   local: what this checkout has
                       └─ hashes/<arch>/<component>.sha256           committed: what is released
kas build (in KAS_IMAGE) ──► yocto/build/<arch>/<component>/ ──aember pack──► build/release/v<VERSION>/ ──► GitHub release
```

`KasBuild.should_build` (`aember/steps/kas/build.py`):

1. `--force` → build.
2. The output is present and the local `.kas-hash` equals the key → skip.
3. The committed `hashes/<arch>/<component>.sha256` differs from the key → no
   release has this artifact → build.
4. Otherwise download the release asset of `v<VERSION>` (see below): a zip is
   extracted into the output dir, the SDK installer is kept as
   `yocto/build/<arch>/sdk-installer.sh` and run into `sdk/`. If that fails →
   build.

After a build, the step checks that the output exists, then writes both the
local marker and `hashes/<arch>/<component>.sha256`. **Commit the `.sha256`
only together with publishing the matching release asset.** A committed hash
promises that the asset exists.

- Version: the `VERSION` file at the repo root (`x.y.z`).
- Repo: parsed from the `origin` git remote. Downloads use `gh` (it needs
  `GITHUB_TOKEN`, which `check_resources.py` can load from
  `tools/scripts/.env`), staged in `build/downloads/`.

### Release assets

The aember repo pulls these assets later to compile and pack the app, so
their names and the manifest format are an interface. Change them in both
repos together. Naming lives in `config/release.py`.

| Asset                                      | Content                                                    |
|--------------------------------------------|------------------------------------------------------------|
| `aember-<component>-<arch>-v<VERSION>.zip` | kernel, busybox, lxc: the whole output dir, incl. `.kas-hash` |
| `aember-sdk-<arch>-v<VERSION>.sh`          | the SDK installer; run it with `-d <dir> -y`               |
| `manifest.json`                            | version, tag, and per asset: component, arch, format, kas hash, sha256, size |
| `SHA256SUMS`                               | `sha256sum -c` list of all assets                          |

- `aember pack [components] -a <arch>` stages assets in
  `build/release/v<VERSION>/` (git-ignored) and regenerates `manifest.json`
  and `SHA256SUMS` over everything packed for that version
  (`steps/release/pack.py`). It refuses a component whose output isn't
  present, whose `.kas-hash` isn't the current key, or whose
  `hashes/<arch>/<c>.sha256` differs. Per-asset metadata goes in `.meta/`,
  which is not uploaded.
- Zips are reproducible (sorted entries, fixed 1980 timestamps), keep Unix
  permission bits, and store symlinks as regular files (lxc's `liblxc.so*`),
  so any unzip tool works. `utils/archive.extract_zip` restores the modes.
- The SDK ships as its installer, not as a zip: the installed tree is ~4 GB
  (GitHub caps assets at 2 GiB), has >1000 symlinks and has its install path
  baked in. The installer relocates itself.
- `aember publish [--clobber]` uploads the staged release
  (`steps/release/publish.py`). It re-checks every asset's sha256 against
  `manifest.json`, requires HEAD to be pushed and HEAD's committed
  `hashes/<arch>/<c>.sha256` to equal each asset's kas hash, then creates
  release `v<VERSION>` at HEAD (if missing) and uploads the assets plus
  `manifest.json`/`SHA256SUMS`. An existing asset is refused unless
  `--clobber`. The order is: build → pack → commit code + `hashes/` → push
  → publish. Only publish when explicitly asked.
- gh auth: `GITHUB_TOKEN`/`GH_TOKEN` in the env, `GITHUB_TOKEN` in
  `tools/scripts/.env` (`utils/github.load_github_token`), or `gh auth login`.
  With a `gh auth login`, `init.sh` also runs `gh auth setup-git` at container
  start, so plain `git push` works.

### Compilers

- **The Poky SDK is the only toolchain** (GCC 15 in the pinned poky). C++
  code targets **C++23** (`-std=c++23` / `CMAKE_CXX_STANDARD 23`).
- `aember build sdk` runs `populate_sdk` in the kas container, copies the
  installer (`yocto/bitbake/tmp/deploy/sdk/*-<machine>-toolchain-*.sh`) to
  `yocto/build/<arch>/sdk-installer.sh` (its release asset), then runs it in
  the dev container with `-d yocto/build/<arch>/sdk -y`, so the SDK's
  relocated paths are dev-container paths. The target sysroots are
  `core2-64-poky-linux`, `cortexa53-poky-linux`,
  `armv7at2hf-neon-poky-linux-gnueabi` and `riscv64imafdc-poky-linux` (tune `riscv64`)
  (`config/sdk.py`).
- The SDK's QEMU is built headless (`PACKAGECONFIG:remove:pn-nativesdk-qemu`
  in `kas/recipes/sdk.yml`). With poky's `opengl` it pulls SDL, virglrenderer
  and mesa, and mesa needs clang/LLVM built twice (~2 h). Check
  `bitbake -g core-image-minimal -c populate_sdk` (`pn-buildlist`) when
  adding SDK packages, so they don't bring clang back.
- `sdk.yml` also caps `BB_NUMBER_THREADS`/`PARALLEL_MAKE`: at 16x16 the big
  C++ compiles got OOM-killed on the 15 GB host.
- **CPU caps (WSL crashes when a build uses every core):** every kas container
  runs with `docker --cpus` = 66% of the host CPUs (`CPU_SHARE` in
  `utils/kas_container.py`, override with `AEMBER_KAS_CPUS=<n>`), and
  `kas/machine/arm64-linux.yml`, `arm-linux.yml` and `riscv64-linux.yml`
  set `PARALLEL_MAKE = "-j 8"` / `BB_NUMBER_THREADS = "8"` for all their
  builds. Keep both.
- The SDK has no `pkg-config`. Poky expects the host's one
  (`nativesdk-sdk-provides-dummy`), so the dev container installs `pkgconf`.
- Extra target libraries go into the SDK through `TOOLCHAIN_TARGET_TASK` in
  `kas/recipes/sdk.yml`: `aember-lxc-dev` (liblxc, headers, `lxc.pc`) and
  `gcc-sanitizers` (v0.1.8: libasan, libubsan; liblsan and libtsan except on
  arm32; the SDK's dev-pkgs add the link-time `.so` and `*_preinit.o`) for
  aember's `aember test --sanitize`. Use it with
  `source yocto/build/<arch>/sdk/environment-setup-<tune>-poky-linux`.
- **Qt 6 in every SDK (v0.1.13)**: `kas/recipes/sdk.yml` adds meta-qt6
  (`6.10`, Qt 6.10.3) and meta-openembedded (meta-oe, meta-python), pinned
  near poky's commit, **only to the SDK chain** (kernel/BusyBox/LXC keys stay).
  qtbase is minimal: `PACKAGECONFIG:pn-qtbase = "gui linuxfb no-opengl png
  zlib"` (Core, Gui, Network; linuxfb/offscreen/minimal/vnc platforms; no
  OpenGL, widgets, ICU, DBus, fontconfig, input). The target sysroot gets
  `qtbase qtbase-dev qtbase-plugins`, the host part `nativesdk-qtbase-tools
  nativesdk-qtbase-dev` (moc, rcc; meta-qt6 hooks into OEToolchainConfig).
  `QT_PTEST_ENABLED = "0"`: poky's ptest would build Qt's whole autotest
  suite (hours per arch). Qt's make jobs are capped at 4 (its cc1plus take
  ~1 GB). Check new Qt features with `bitbake -g` for clang/mesa first.
  Used by aember-monitor.
- **No gcc-reflection** and no other custom GCC builds. That's a deliberate
  decision, so don't reintroduce it.

## Repository layout

```
.devcontainer/          Dev container (Ubuntu 26.04 Yocto build host)
aember-cli/             Python CLI (`aember`), installed editable in /venv
  aember/cli/           Typer commands (app.py wires them up, one file per command)
  aember/core/          Context, Step, Pipeline
  aember/steps/kas/     KasBuild: the CAS-cached component build
  aember/steps/release/ PackComponent, WriteReleaseIndex, PublishRelease
  aember/steps/linting/ LintStep
  aember/config/        components.py (kas chains), release.py (asset names), arch, SDK, QEMU, libs/modules
  tests/                unittest: test_architectures.py (every arch complete everywhere)
  aember/utils/         kas_container (docker run), kas_hash, fetch_artifact, archive (zip), github, root, runner
kas/                    kas YAML files (see above)
meta-aember/            Yocto layer: machines + kernel/busybox/lxc recipes
hashes/<arch>/          Committed CAS keys of released artifacts
VERSION                 Release version (x.y.z)
.github/workflows/      ci.yml: CLI tests + lint on push and pull requests
tools/scripts/          init.sh (container postStart), prerequisites.sh (host setup)
requirements.txt        Python tooling pinned for the venv (incl. kas)
yocto/                  git-ignored kas work dir: poky/ clone, bitbake/,
                        downloads/, sstate-cache/, build/<arch>/<component>/
build/                  git-ignored: downloads/ (fetched assets), release/v<VERSION>/ (packed)
```

`aember-cli/.git` is a gitdir pointer (`../.git/modules/aember-cli`), but
there's no `.gitmodules`, and its files are tracked directly by this repo.
Don't "fix" this without asking.

## Environment

- Work happens inside the dev container. The workspace is mounted at
  `/aember_ws/aember-resources`, and the venv is `/venv` (on `PATH`). The
  aember repo sits next to it at `/aember_ws/aember`.
- `HOST_ROOT_PATH` (set by devcontainer.json) is the host path of the repo.
  The kas container mount depends on it, and outside the dev container it
  falls back to the repo root.
- Docker is reached through the host socket. The kas image is pulled on
  first use.
- `tools/scripts/.env` can contain `GITHUB_TOKEN` and is git-ignored. **Never
  commit it, print it, or copy secrets into code.**
- Yocto builds take a long time (hours the first time) and use a lot of disk
  (16 cores / 15 GB RAM in the container). Don't start `kas build`/`aember
  build` without the user asking. For quick checks, prefer `kas dump` or
  `kas shell -c "bitbake -e <target>"`.
- Don't kill a running build mid-compile unless you have to. An interrupted
  `do_compile` can leave truncated object files that `make` later treats as
  up to date (symptom: odd link errors like "undefined reference to `main`").
  If you did stop one, run `bitbake -c clean <recipe>` for the failing recipe
  through `aember kas-shell` and rebuild.
- Run git from the repo root: inside `aember-cli/`, git follows the broken
  `.git` pointer and fails.

## Commands

```bash
aember --help                # list commands
aember -v <cmd>              # verbose (DEBUG) logging
aember build kernel busybox lxc sdk --arch x64-poky-linux   # CAS-cached kas builds
aember build kernel busybox lxc sdk -a x64-poky-linux -a arm-poky-linux  # -a is repeatable
aember build kernel -a aarch64-poky-linux --force            # rebuild ignoring the cache
aember pack -a x64-poky-linux -a aarch64-poky-linux -a arm-poky-linux  # stage release assets (no upload)
aember publish                                               # upload build/release/v<VERSION>/ to GitHub
aember kas-shell lxc -a x64-poky-linux                       # bitbake shell in the kas image
aember lint                  # ruff --fix + black + clang-format + cmake-format/cmakelint
python aember-cli/run.py ... # run the CLI without the installed entry point
```

## Coding conventions (aember-cli)

- Tests: `cd aember-cli && python -m unittest discover -s tests` (stdlib).
  A new architecture must pass `tests/test_architectures.py` before its
  first Yocto build: it checks the CLI maps, kas and Yocto machine files,
  the kernel/BusyBox/LXC configuration and every recipe's
  `COMPATIBLE_MACHINE`.

- Python ≥ 3.10 syntax. Line length is 88, formatting is **black**, linting is
  **ruff**, isort uses the `black` profile. Run `aember lint` before finishing.
- **A new build is a Step plus a CLI command:**
  1. `aember/steps/<area>/<name>.py`: subclass `Step`, implement
     `run(self, ctx: Context)`, and put the cache decision in `should_build(ctx)`.
  2. `aember/cli/<group>/<name>.py`: a thin Typer function that builds a
     `Context` and runs a `Pipeline([...])`, with no logic of its own.
  3. Register it in `aember/cli/app.py`.
- Steps run kas only through `utils/kas_container.run_kas(root, cmd, chain)`.
  Other commands go through `CommandRunner.run([...])` with an argument list. Per-arch and per-component data belong in `aember/config/`,
  keyed by the arch string. Raise a `ValueError` that lists the known keys when
  a key is missing.
- Commands find the repo root with `utils/root.find_root()` (it looks for
  `kas/base.yml`), not with `Path.cwd()`.
- Use the `Architecture` / `BuildType` enums for CLI options.
- Logging: `log = logging.getLogger("aember.<area>")`. Use `%s` args in log
  calls, not f-strings.
- Fetch helpers return `bool` and log warnings instead of raising, so callers
  can fall back to building from source. Keep that contract.
- Build paths from `ctx.root` (`pathlib.Path`). `aember/config/libs.py` still
  has hard-coded `/aember_ws/aember/...` paths from the old setup (unused for
  now).
- Steps must be idempotent. Clear temp dirs with
  `shutil.rmtree(..., ignore_errors=True)` before using them.

## YAML conventions

- 2-space indent, `.yml` extension, lowercase-hyphen file names.
- Comment each `local_conf_header` block with *why* the setting exists.
- Changing any kas file changes the CAS key. Rebuild, then commit the new
  `.sha256` together with the released artifact.

## Working agreements for agents

- `TODO.md` (repo root) lists collected ideas and known gaps. Read it for
  context, but implement an item only when the user asks for it; update it
  when an item is done or a new one comes up.
- Commit only when asked, and branch off `main` first.
- Confirm before deleting or overwriting anything under `yocto/build/`, the
  hashes dir, `resources/` or `build/`. Those are expensive to regenerate.
- Don't commit `hashes/**.sha256` without a matching published asset, and
  don't publish GitHub releases or upload assets unless explicitly asked.
- When something in this file goes stale (for example, once the kas files
  land), update this file in the same change.
