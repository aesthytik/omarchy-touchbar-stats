#!/usr/bin/env bash
# Undoes setup.sh.
source "$(dirname "$(readlink -f "$0")")/lib.sh"

say "Stopping the stats"
systemctl --user stop "$USER_UNIT" 2>/dev/null || true
rm -f "$USER_UNIT_DIR/$USER_UNIT"
systemctl --user daemon-reload

say "Removing the $STATS_KEYS binding"
remove_binding
reload_hyprland

say "Releasing tiny-dfr-plus"
as_root "$PLUGIN_DIR/tiny-dfr-plus-root.sh" release "$PLUGIN_ID"
plus_clean_cache

say "Removed."
