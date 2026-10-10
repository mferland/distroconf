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

## Manual

### Workstation setup

- [Omarchy overview](omarchy.org): managed configuration and optional setup.
- [Disk swap](swap.org): RAM-sized Btrfs swap, activation, and verification.
- [Hardware](hardware.org): optional keyboard firmware mapping.

### Access and networking

- [SSH](ssh.org): client keys, the user agent, Git hosts, and optional server setup.
- [YubiKey](yubikey.org): security-key enrollment, SSH connection reuse, PAM,
  and smart-card integration.
- [Network mounts](mounts.org): home NAS over NFS and work SAPFS over CIFS.

### Development and testing

- [kas and Podman](kas.org): rootless Yocto builds with writable repositories.
- [Emacs integrations](emacs.org): optional RTags setup.
- [VM testing](vm.org): installation, iteration, diagnostics, and acceptance checks.
