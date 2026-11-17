# Touch Bar Stats

Your AI usage and your machine's vitals across the MacBook Touch Bar.

- **AI**: for each signed-in agent (Claude Code, Codex and others that report limits), its
  usage limits as meters with percentages, such as Claude's 5-hour session and weekly
  limits, plus today's tokens.
- **System**: CPU, RAM, CPU temperature, battery (with a bolt while charging), network
  download and upload speed, and the time.

**Super + Ctrl + Alt + S** shows the stats; press it again, or tap the bar, to hide them.
While they're showing they use the whole Touch Bar; your normal keys come back as soon
as you hide them.

## Where the numbers come from

- AI limits come from the usage records Omarchy's **Agents** panel keeps in
  `~/.local/state/omarchy/agents/usage/`. If they're more than five minutes old when you
  open the stats, the plugin asks Omarchy to refresh them
  (`omarchy agent usage update --limits-only`) and shows the new numbers when they land.
  A yellow `*` means Omarchy couldn't refresh that agent and the numbers are old.
- System stats are read once a second from `/proc` and `/sys`.

Nothing leaves your machine except Omarchy's own limit refresh, which is the same request
its Agents panel makes.

## Requirements

- An Intel MacBook Pro with a Touch Bar (T2), running Omarchy with the `linux-t2` kernel
- `tiny-dfr` from the `arch-mact2` repo, already working
- `python-cairo` for drawing, plus `rust` and `git` to build tiny-dfr-plus (setup installs
  whichever are missing)

## Install

```bash
omarchy plugin add https://github.com/aesthytik/omarchy-touchbar-stats --enable
~/.config/omarchy/plugins/io.github.aesthytik.touchbar-stats/setup.sh
```

Setup lists what it will change and asks before doing anything (pass `--yes` to skip the
question). It needs your password once. It:

1. installs `python-cairo`, `rust` and `git` if they're missing;
2. builds **tiny-dfr-plus** in `~/.cache/tiny-dfr-plus/`: tiny-dfr at a pinned commit
   plus `tiny-dfr-plus.patch` (takes a minute or two the first time);
3. installs it as `/usr/local/bin/tiny-dfr-plus` and points `tiny-dfr.service` at it with
   the drop-in `/etc/systemd/system/tiny-dfr.service.d/50-tiny-dfr-plus.conf`; the packaged
   `/usr/bin/tiny-dfr` is left untouched;
4. adds the user service `touchbar-stats.service`, which only runs while the stats are
   showing;
5. adds the Super + Ctrl + Alt + S binding to `~/.config/hypr/bindings.lua`, between
   marker comments.

After a `tiny-dfr` package update, run setup again to rebuild.

## Works with the other Touch Bar plugins

tiny-dfr-plus is shared with
[Touch Bar Waveform](https://github.com/aesthytik/omarchy-touchbar-waveform) and
[Box Cat](https://github.com/aesthytik/omarchy-touchbar-cat). Each plugin registers in
`/etc/tiny-dfr/plus.d/`, and the stock tiny-dfr comes back when the last one is removed.
The stats and Box Cat both use the whole bar, so opening one closes the other.

The stats draw through tiny-dfr-plus's takeover socket (`/run/tiny-dfr/takeover.sock`): 1085×30
pixels, scaled 2× to the bar's 2170×60. While they're showing, tiny-dfr sends back only
touches on the bar and Esc/Space/Up/Down presses; the stats only use the touches.

### Who can use the sockets

tiny-dfr-plus's sockets are files in `/run/tiny-dfr/`, a directory systemd creates for
the daemon and only root can write to, so no other account can claim their names first.
For every frame the kernel tells the daemon which user sent it; frames from anyone but
the user logged in at the screen (or root) are dropped, and only that user is sent key
and touch events. Programs check that events come from `/run/tiny-dfr/…` before using
them.

The same patch has a full-colour backdrop socket (`/run/tiny-dfr/backdrop.sock`) used by
Touch Bar Scenes, with the same checks. Its key-column events, which say roughly where on
the keyboard a key was pressed but never which key, are off unless `KeyPulses = true` is
set in `/etc/tiny-dfr/config.toml`.

The patch is built from a fixed upstream tiny-dfr commit (`a79f2f4`), fetched by its full
SHA and checked out detached before building.

## Remove

```bash
~/.config/omarchy/plugins/io.github.aesthytik.touchbar-stats/remove.sh
omarchy plugin remove io.github.aesthytik.touchbar-stats
```

Remove stops and deletes the stats service, removes the binding and releases
tiny-dfr-plus. `python-cairo` and `rust` stay installed; remove them with pacman if you
don't need them.

## Credits

`preview.png` shows a real frame from the plugin.

## License

MIT. The patch applies to tiny-dfr, which is MIT and Apache-2.0 licensed.
