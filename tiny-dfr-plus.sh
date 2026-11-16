# tiny-dfr-plus: tiny-dfr with Visualizer buttons and full-bar takeover.
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
  if [[ ! -d $src/.git ]]; then
    mkdir -p "$PLUS_CACHE"
    git clone --quiet "$PLUS_REPO" "$src"
  fi
  git -C "$src" fetch --quiet origin "$PLUS_COMMIT" 2>/dev/null || true
  git -C "$src" checkout --quiet --force "$PLUS_COMMIT"
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
