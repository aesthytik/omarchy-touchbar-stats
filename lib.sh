# Shared helpers for setup.sh and remove.sh. Sourced, not executed.
set -euo pipefail

PLUGIN_ID=io.github.aesthytik.touchbar-stats
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PLUGIN_DIR/tiny-dfr-plus.sh"
BINDINGS="${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua"
MARK_BEGIN="-- >>> $PLUGIN_ID >>>"
MARK_END="-- <<< $PLUGIN_ID <<<"
STATS_KEYS="SUPER + CTRL + ALT + S"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
USER_UNIT=touchbar-stats.service

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

# sudo in a terminal, pkexec when there's no terminal to type a password into.
as_root() {
  if [[ $EUID -eq 0 ]]; then "$@"
  elif [[ -t 0 ]]; then sudo "$@"
  else pkexec "$@"
  fi
}

remove_binding() {
  [[ -f $BINDINGS ]] || return 0
  local b e
  b="$(printf '%s' "$MARK_BEGIN" | sed 's/[]\/$*.^[]/\\&/g')"
  e="$(printf '%s' "$MARK_END" | sed 's/[]\/$*.^[]/\\&/g')"
  sed -i "/^$b\$/,/^$e\$/d" "$BINDINGS"
}

reload_hyprland() {
  command -v hyprctl >/dev/null || return 0
  hyprctl reload >/dev/null
  local errs; errs="$(hyprctl configerrors 2>/dev/null || true)"
  [[ -z ${errs//[[:space:]]/} ]] || printf 'Hyprland config errors:\n%s\n' "$errs" >&2
}
