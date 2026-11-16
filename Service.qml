import QtQuick
import Quickshell.Io

// Checks whether Touch Bar Stats is set up. The stats run as their own user service,
// shown and hidden with Super+Ctrl+Alt+S, and draw through tiny-dfr-plus;
// setup.sh installs both, because a shell plugin can't change system files.
Item {
  id: root

  // Injected by omarchy-shell.
  property var shell: null

  property bool checked: false
  property bool daemonPatched: false
  property bool serviceInstalled: false
  readonly property bool ready: daemonPatched && serviceInstalled

  function refresh() {
    if (!probe.running) probe.running = true
  }

  Component.onCompleted: refresh()

  Process {
    id: probe
    command: ["bash", "-c",
      "systemctl show tiny-dfr.service -p ExecStart --value 2>/dev/null | grep -q tiny-dfr-plus && echo daemon; " +
      "systemctl --user cat touchbar-stats.service >/dev/null 2>&1 && echo service; true"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        const lines = text.split("\n")
        root.daemonPatched = lines.indexOf("daemon") !== -1
        root.serviceInstalled = lines.indexOf("service") !== -1
        root.checked = true
        if (!root.ready)
          console.warn("[touchbar-stats] not fully set up; run setup.sh in the plugin folder")
      }
    }
  }
}
