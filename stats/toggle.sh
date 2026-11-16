#!/usr/bin/env bash
# Super+Ctrl+Alt+S: show the stats on the Touch Bar, or hide them again.
if systemctl --user is-active --quiet touchbar-stats.service; then
  systemctl --user stop touchbar-stats.service
else
  systemctl --user start touchbar-stats.service
fi
