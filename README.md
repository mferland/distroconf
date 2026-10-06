# distroconf

Personal Omarchy, Hyprland, Emacs, Git, and shell configuration.

## Restore on a new Omarchy installation

```sh
git clone git@github.com:mferland/distroconf.git ~/dev/distroconf
~/dev/distroconf/bootstrap.sh
```

The bootstrap is safe to rerun. Before replacing an unmanaged target, it
moves that target into a timestamped directory under
`~/.local/state/distroconf/backups/`. GNU Stow owns the files in `dotfiles/`;
the Emacs configuration and launcher are linked explicitly; the SSH client
configuration is installed with mode `0600`. The Emacs unit is
installed as a regular file because `systemctl reenable` removes linked units.

It restores:

- user-owned Arch and AUR package selections;
- Hyprland look-and-feel, including fully opaque windows;
- Omarchy shell layout, default agent, theme, font, and background;
- reviewed Omarchy shell plugins pinned in `plugins/omarchy.tsv`;
- Git and shell configuration;
- Emacs configuration and local modes;
- SSH-agent integration and the Emacs user service;
- the `edit` Emacs launcher in `~/bin`.

Generated Omarchy theme files, caches, private keys, browser data, Wi-Fi
credentials, and machine-specific system configuration are deliberately not
tracked. Privileged or hardware-specific setup remains documented in the Org
files; [omarchy.org](omarchy.org) documents the optional workstation setup.

## Manual system setup

- [SSH](ssh.org) covers client keys, the user agent, Git hosts, YubiKey-backed
  credentials, backups, and optional client and server settings.
- [YubiKey 5 NFC](yubikey.org) covers FIDO2/WebAuthn and optional PAM and
  smart-card integration.
- [Network mounts](mounts.org) covers location-aware NFS mounts for the home
  NAS and the SAPFS CIFS mount for the work network.

## RAM-sized disk swap

Omarchy already provides RAM-sized compressed zram. To add the same amount
of swap on disk, follow [the swap instructions](omarchy.org#ram-sized-disk-swap):

```sh
./setup-swap.sh                 # Preview
sudo ./setup-swap.sh --apply    # Create, activate, and enable at boot
```

This optional Btrfs setup keeps zram preferred and does not enable hibernation.
It is separate from bootstrap. Test it inside the VM before using it on a workstation.

## Test configuration changes in an Omarchy VM

`vm-test.sh` installs a dedicated Omarchy guest and preserves a clean baseline.
Baseline preparation uses `omarchy update -y` before saving the image.
Each full test boots a fresh disk overlay with its own UEFI variables. Your
host checkout is copied into the guest, including uncommitted changes and new
non-ignored files; it is never mounted writable.

On the host, install any missing dependencies:

```sh
omarchy pkg add qemu-desktop edk2-ovmf cdrtools rsync python openssh
```

Enable AMD-V/VT-x in firmware and verify your user can access `/dev/kvm`.
Run the script from your graphical desktop session: the VM uses a GTK console
with VirtIO 3D acceleration. The defaults are 4 CPUs, 8 GB RAM, a 60 GB sparse
disk, and localhost SSH port 2322. Allow at least 15 GB free initially and
monitor disk usage as test runs accumulate.

Download the official **stable Omarchy 4.x ISO** and its `.sha256` sidecar from
[omarchy.org](https://omarchy.org). Keep their original filenames together.
The unattended configuration targets the Omarchy 4 installer; older 3.x,
development, and release-candidate images are rejected.

```sh
# Install once; validate the checksum and save a clean baseline.
./vm-test.sh init --iso ~/Downloads/omarchy-4.0.4.iso

# Fresh baseline, current edits, bootstrap twice, reboot, acceptance checks.
./vm-test.sh test

# Fast iteration: update the existing guest and run bootstrap once.
./vm-test.sh apply

# Inspect or operate the current test guest.
./vm-test.sh status
./vm-test.sh ssh
./vm-test.sh stop
./vm-test.sh start
```

You can also begin with `./vm-test.sh test --iso PATH`, which installs the
baseline automatically on the first run. Later tests reuse that baseline;
package downloads during bootstrap still depend on the current Arch/AUR
repositories. AUR failures produce warnings, matching bootstrap's existing
optional-AUR policy.

Guest setup uses desktop autologin and passwordless sudo for the dedicated
`omarchy` test user. No host SSH credentials are copied or forwarded. The
script creates its own SSH identity, guest password, and known-hosts file.
These and VM files live in `~/.local/state/distroconf/vm/`, outside the repo.
Only the guest has passwordless sudo; never run this script with host sudo.

Both success and failure leave the VM available for inspection. Logs,
serial output, diagnostics, and a console screenshot (`console.png`, with `console.ppm` as a QEMU fallback) are saved
under the state directory's `runs/`. Each bootstrap/check log has a unique
name. A clean test stops the previous VM gracefully; it refuses to discard a
running guest that will not shut down. Old run directories remain available
and must be removed manually when no longer needed, with the VM stopped.

Automated checks cover managed links, preserved backups, packages, pinned
plugins, Emacs and SSH-agent services, Hyprland configuration, repeatability,
and post-reboot health. Inspect theme, font, background, menus, and interactive
behavior visually in the VM window. YubiKey and hardware-specific instructions
remain manual; the automated setup target is `bootstrap.sh`.

Use `--state-dir PATH` on every command to maintain another independent
baseline or recover from an incomplete installation without overwriting it.
Use `--port NUMBER` during installation for a different localhost port (the
baseline and active VM remember it). Firmware paths can be overridden with `--ovmf-code`
and `--ovmf-vars` on machines with a different OVMF layout. `--help` lists
all options. Installation waits up to 40 minutes, boot up to 10 minutes, and
each bootstrap/check operation up to one hour; timeout failures preserve logs.

Run the host-side automation checks without starting a VM:

```sh
python3 -m unittest discover -s tests -v
```
