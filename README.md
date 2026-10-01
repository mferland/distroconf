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
the existing top-level Emacs, SSH, and helper-script sources are installed or
linked explicitly to preserve the repository's established layout. The Emacs
unit is installed as a regular file because `systemctl reenable` removes
linked units, and the SSH client config is installed with mode `0600`.

It restores:

- user-owned Arch and AUR package selections;
- Hyprland look-and-feel, including fully opaque windows;
- Omarchy shell layout, default agent, theme, font, and background;
- reviewed Omarchy shell plugins pinned in `plugins/omarchy.tsv`;
- Git and shell configuration;
- Emacs configuration and local modes;
- SSH-agent integration and the Emacs user service;
- personal scripts in `~/bin`.

Generated Omarchy theme files, caches, private keys, browser data, Wi-Fi
credentials, and machine-specific system configuration are deliberately not
tracked. Privileged or hardware-specific setup remains documented in the Org
files.

## Manual system setup

- [SSH](ssh.org) covers client keys, the user agent, Git hosts, YubiKey-backed
  credentials, backups, and optional client and server settings.
- [YubiKey 5 NFC](yubikey.org) covers FIDO2/WebAuthn and optional PAM and
  smart-card integration.
- [Network mounts](mounts.org) covers location-aware NFS mounts for the home
  NAS and the SAPFS CIFS mount for the work network.
