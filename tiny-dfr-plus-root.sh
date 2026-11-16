#!/bin/sh
# Root half of tiny-dfr-plus.sh. Run through sudo/pkexec by the plugins' scripts.
#   tiny-dfr-plus-root.sh install <plugin-id> <built-binary> [command...]
#   tiny-dfr-plus-root.sh release <plugin-id> [command...]
# The optional command (a Touch Bar config edit) runs as root before tiny-dfr restarts.
set -eu
BIN=/usr/local/bin/tiny-dfr-plus
DROPIN_DIR=/etc/systemd/system/tiny-dfr.service.d
DROPIN=$DROPIN_DIR/50-tiny-dfr-plus.conf
USERS=/etc/tiny-dfr/plus.d

cmd=$1 id=$2
case $id in */*|.*|"") echo "bad plugin id" >&2; exit 1 ;; esac
case $cmd in
  install)
    built=$3; shift 3
    install -Dm755 "$built" "$BIN"
    mkdir -p "$DROPIN_DIR" "$USERS"
    printf '[Service]\nExecStart=\nExecStart=%s\n' "$BIN" >"$DROPIN"
    : >"$USERS/$id"
    # Touch Bar Waveform 0.1 installed its own copy; tiny-dfr-plus replaces it.
    rm -f /usr/local/bin/tiny-dfr-waveform "$DROPIN_DIR/50-touchbar-waveform.conf"
    ;;
  release)
    shift 2
    rm -f "$USERS/$id"
    if [ -z "$(ls -A "$USERS" 2>/dev/null)" ]; then
      rm -f "$BIN" "$DROPIN"
      rmdir "$USERS" "$DROPIN_DIR" 2>/dev/null || true
    fi
    ;;
  *) echo "usage: $0 install|release <plugin-id> ..." >&2; exit 1 ;;
esac
if [ $# -gt 0 ]; then "$@"; fi
systemctl daemon-reload
systemctl restart tiny-dfr.service || true
