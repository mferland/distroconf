#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
timestamp=$(date +%Y%m%d-%H%M%S)
backup_dir="$state_home/distroconf/backups/$timestamp"
made_backup=false

log() {
  printf 'distroconf: %s\n' "$*"
}

warn() {
  printf 'distroconf: warning: %s\n' "$*" >&2
}

backup_target() {
  local target=$1 resolved relative destination

  [[ -e "$target" || -L "$target" ]] || return 0

  if [[ -L "$target" ]]; then
    resolved=$(readlink -f -- "$target" 2>/dev/null || true)
    if [[ "$resolved" == "$repo_dir"/* ]]; then
      return 0
    fi
  fi

  relative=${target#"$HOME"/}
  destination="$backup_dir/$relative"
  mkdir -p -- "$(dirname -- "$destination")"
  mv -- "$target" "$destination"
  made_backup=true
  log "backed up $target"
}

read_manifest() {
  local manifest=$1 line
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    line=${line//[[:space:]]/}
    [[ -n "$line" ]] && printf '%s\n' "$line"
  done < "$manifest"
}

install_packages() {
  local -a arch_packages aur_packages
  mapfile -t arch_packages < <(read_manifest "$repo_dir/packages/arch.txt")
  mapfile -t aur_packages < <(read_manifest "$repo_dir/packages/aur.txt")

  if ((${#arch_packages[@]})); then
    log "installing official packages"
    omarchy pkg add "${arch_packages[@]}"
  fi

  if ((${#aur_packages[@]})); then
    if omarchy pkg aur accessible >/dev/null 2>&1; then
      log "installing AUR packages"
      omarchy pkg aur add "${aur_packages[@]}" || warn "some AUR packages could not be installed"
    else
      warn "AUR is unavailable; skipped ${aur_packages[*]}"
    fi
  fi
}

link_repo_file() {
  local source=$1 target=$2
  mkdir -p -- "$(dirname -- "$target")"
  backup_target "$target"
  ln -sfn -- "$source" "$target"
}

install_repo_file() {
  local source=$1 target=$2 mode=${3:-0644} resolved
  mkdir -p -- "$(dirname -- "$target")"

  if [[ -f "$target" && ! -L "$target" ]] && cmp -s -- "$source" "$target"; then
    chmod "$mode" "$target"
    return 0
  fi

  if [[ -L "$target" ]]; then
    resolved=$(readlink -f -- "$target" 2>/dev/null || true)
    if [[ "$resolved" == "$repo_dir"/* ]]; then
      unlink -- "$target"
    else
      backup_target "$target"
    fi
  else
    backup_target "$target"
  fi

  install -m "$mode" -- "$source" "$target"
}

sync_checkout() {
  local name=$1 url=$2 target
  target="$HOME/.emacs.d/site-lisp/$name"

  if [[ -d "$target/.git" ]]; then
    if [[ -z $(git -C "$target" status --porcelain) ]]; then
      git -C "$target" pull --ff-only
    else
      warn "$target has local changes; leaving it unchanged"
    fi
  else
    backup_target "$target"
    git clone -- "$url" "$target"
  fi
}

sync_omarchy_plugins() {
  local manifest="$repo_dir/plugins/omarchy.tsv"
  local id url commit target

  [[ -f "$manifest" ]] || return 0
  mkdir -p -- "$HOME/.config/omarchy/plugins"

  while IFS=$'\t' read -r id url commit || [[ -n "$id$url$commit" ]]; do
    [[ -z "$id" || "$id" == \#* ]] && continue
    target="$HOME/.config/omarchy/plugins/$id"

    if [[ -e "$target" && ! -d "$target/.git" ]]; then
      backup_target "$target"
    fi

    if [[ ! -d "$target/.git" ]]; then
      git clone --no-checkout -- "$url" "$target"
    elif [[ -n $(git -C "$target" status --porcelain) ]]; then
      warn "$target has local changes; leaving it unchanged"
      continue
    fi

    git -C "$target" fetch --quiet origin
    git -C "$target" checkout --quiet --detach "$commit"
    omarchy plugin validate "$target"
    log "installed Omarchy plugin $id at $commit"
  done < "$manifest"
}

install_packages

for target in \
  "$HOME/.bash_profile" \
  "$HOME/.config/git/config" \
  "$HOME/.config/hypr/input.lua" \
  "$HOME/.config/hypr/looknfeel.lua" \
  "$HOME/.config/omarchy/shell.json" \
  "$HOME/.config/omarchy/shell.toml" \
  "$HOME/.config/omarchy/defaults/agent" \
  "$HOME/.config/omarchy/backgrounds/everforest/lamborghini-aventador-svj-lamborghini-aventador-svj-dve-mash.jpg"
do
  backup_target "$target"
done

log "linking dotfiles"
stow --restow --no-folding --dir "$repo_dir" --target "$HOME" dotfiles
sync_omarchy_plugins

link_repo_file "$repo_dir/init.el" "$HOME/.emacs.d/init.el"
install_repo_file "$repo_dir/ssh.config" "$HOME/.ssh/config" 0600
install_repo_file "$repo_dir/emacs.service" "$HOME/.config/systemd/user/emacs.service"

mkdir -p -- "$HOME/bin" "$HOME/.saves" "$HOME/.emacs.d/site-lisp"
# Remove dangling launchers owned by an earlier checkout of this repository.
for target in "$HOME/bin/"*; do
  if [[ -L "$target" && ! -e "$target" ]]; then
    source=$(readlink -- "$target")
    if [[ "$source" == "$repo_dir/"* ]]; then
      unlink -- "$target"
      log "removed obsolete launcher $target"
    fi
  fi
done
link_repo_file "$repo_dir/edit" "$HOME/bin/edit"

sync_checkout bb-mode https://github.com/mferland/bb-mode.git
sync_checkout flex https://github.com/manateelazycat/flex.git
sync_checkout bison https://github.com/manateelazycat/bison.git

log "installing Emacs package dependencies"
emacs -Q --batch -l "$HOME/.emacs.d/init.el"

log "configuring user services"
systemctl --user daemon-reload
systemctl --user enable --now ssh-agent.socket
systemctl --user reenable emacs.service
if ! systemctl --user is-active --quiet emacs.service; then
  systemctl --user start emacs.service
else
  log "Emacs is already running; restart it later to pick up service changes"
fi

log "restoring Omarchy presentation settings"
omarchy theme set everforest
omarchy font set "JetBrainsMono Nerd Font"
omarchy theme bg set "$HOME/.config/omarchy/backgrounds/everforest/lamborghini-aventador-svj-lamborghini-aventador-svj-dve-mash.jpg"
omarchy restart shell

if command -v hyprctl >/dev/null 2>&1 && [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
  hyprctl reload
  config_errors=$(hyprctl configerrors)
  if [[ -n "$config_errors" ]]; then
    printf '%s\n' "$config_errors" >&2
    exit 1
  fi
else
  warn "Hyprland is not active; skipped live reload and validation"
fi

if [[ "$made_backup" == true ]]; then
  log "previous files are in $backup_dir"
fi
log "setup complete"
