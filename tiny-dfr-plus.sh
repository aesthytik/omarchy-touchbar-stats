# tiny-dfr-plus: tiny-dfr with Visualizer buttons, full-bar takeover and a
# full-colour backdrop, served on sockets in /run/tiny-dfr to the user at the
# screen only.
# Shared by the aesthytik Touch Bar plugins; keep this file and
# tiny-dfr-plus.patch identical across them. Sourced, not executed.
#
# Each plugin that needs it registers in /etc/tiny-dfr/plus.d/<plugin-id>; the
# patched daemon is removed again when the last plugin releases it.

PLUS_REPO=https://github.com/AsahiLinux/tiny-dfr
PLUS_COMMIT=a79f2f43e6c6a9b855968e54eb243c20642ebc89
PLUS_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/tiny-dfr-plus"

# Builds the patched daemon (skipped when this exact patch is already built)
# and prints the path of the binary.
plus_build() {
  local patch="$1" src="$PLUS_CACHE/tiny-dfr" stamp
  stamp="$(sha256sum "$patch" | cut -d' ' -f1)"
  if [[ -x $src/target/release/tiny-dfr && "$(cat "$PLUS_CACHE/built" 2>/dev/null)" == "$stamp" ]]; then
    echo "$src/target/release/tiny-dfr"; return
  fi
  # Build only the exact upstream commit the patch was written against.
  [[ $PLUS_COMMIT =~ ^[0-9a-f]{40}$ ]] || { echo "tiny-dfr-plus: PLUS_COMMIT must be a full commit SHA" >&2; return 1; }
  if [[ ! -d $src/.git ]]; then
    mkdir -p "$src"
    git -C "$src" init --quiet
  fi
  git -C "$src" fetch --quiet --depth 1 "$PLUS_REPO" "$PLUS_COMMIT"
  git -C "$src" checkout --quiet --force --detach "$PLUS_COMMIT"
  [[ "$(git -C "$src" rev-parse HEAD)" == "$PLUS_COMMIT" ]] || { echo "tiny-dfr-plus: checkout is not $PLUS_COMMIT" >&2; return 1; }
  git -C "$src" clean --quiet -fdx -e target
  git -C "$src" apply "$patch"
  cargo build --quiet --release --locked --manifest-path "$src/Cargo.toml" >&2
  echo "$stamp" >"$PLUS_CACHE/built"
  echo "$src/target/release/tiny-dfr"
}

# Deletes the build cache once no plugin uses tiny-dfr-plus any more.
plus_clean_cache() {
  [[ -d /etc/tiny-dfr/plus.d ]] && [[ -n "$(ls -A /etc/tiny-dfr/plus.d 2>/dev/null)" ]] && return 0
  rm -rf "$PLUS_CACHE"
}
