"""Subprocess harness used by integration and endurance checks (Python 3.11+)."""

from __future__ import annotations
import hashlib, json, os, pathlib, shutil, signal, subprocess, time, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Adopt only this harness's orphaned descendants after intentional API crashes,
# allowing exact waitpid reaping even when the environment's PID 1 is minimal.
if os.name == "posix" and pathlib.Path("/proc").is_dir():
    import ctypes

    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError("Cannot enable child subreaper for crash tests")


def freeze(root: pathlib.Path, destination: pathlib.Path):
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "api.jar": root / "control-api/target/control-api-0.1.0.jar",
        "chronicle": root / "chronicle/target/release/foundry-chronicle",
        "dispatch": root / "dispatch/build/foundry-dispatch",
    }
    manifest = {}
    for name, source in files.items():
        shutil.copy2(source, destination / name)
        manifest[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    (destination / "identity.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class Server:
    def __init__(
        self,
        binaries: pathlib.Path,
        data: pathlib.Path,
        web_root: pathlib.Path = ROOT,
        java_options=(),
    ):
        self.java_options = list(java_options)
        self.binaries = binaries
        self.data = data
        self.root = web_root
        self.process = None
        self.log = None
        self.base = None

    def start(self):
        if self.process and self.process.poll() is None:
            raise RuntimeError("Server already running")
        self.data.mkdir(parents=True, exist_ok=True)
        self.log = open(self.data / "server.log", "ab", buffering=0)
        # A unique stdout pipe gives us the actual bound port, without racy
        # port reservation or assuming a saved PID still belongs to us.
        self.process = subprocess.Popen(
            [
                "java",
                *self.java_options,
                "-jar",
                str(self.binaries / "api.jar"),
                "--root",
                str(self.root),
                "--data",
                str(self.data),
                "--port",
                "0",
                "--chronicle",
                str(self.binaries / "chronicle"),
                "--dispatch",
                str(self.binaries / "dispatch"),
            ],
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
        )
        import selectors

        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            if not selector.select(12):
                raise RuntimeError("API startup timeout")
            line = self.process.stdout.readline().strip()
            if "http://127.0.0.1:" not in line:
                raise RuntimeError("API did not announce a listening URL: " + line)
            self.base = line.split()[-1]
        finally:
            selector.close()
        return self

    def get(self, path="/api/state"):
        with urllib.request.urlopen(self.base + path, timeout=8) as r:
            return json.load(r)

    def post(self, operation, body):
        request = urllib.request.Request(
            self.base + "/api/" + operation,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def command(self, operation, command_id, **extra):
        revision = self.get()["revision"]
        status, response = self.post(
            operation, {"commandId": command_id, "expectedRevision": revision, **extra}
        )
        assert status == 200, (status, response)
        return response

    def children(self):
        if not pathlib.Path("/proc").is_dir():
            raise RuntimeError("Crash fault checks require Linux /proc")
        result = {}
        # Some managed procfs views omit /proc/PID/task entirely. procps can
        # still report direct children from the process table.
        found = subprocess.run(
            ["ps", "--ppid", str(self.process.pid), "-o", "pid="],
            capture_output=True,
            text=True,
        )
        pids = found.stdout.split()
        for pid in pids:
            try:
                exe = pathlib.Path(f"/proc/{pid}/exe").resolve(strict=True)
            except FileNotFoundError:
                continue
            if exe.parent == self.binaries.resolve():
                result[exe.name] = int(pid)
        return result

    def kill_child(self, name):
        pid = self.children()[name]
        # A pidfd pins this exact process identity across the signal operation.
        with os.fdopen(os.pidfd_open(pid), "rb") as fd:
            signal.pidfd_send_signal(fd.fileno(), signal.SIGKILL)

    def stop(self, crash=False):
        if self.process and self.process.poll() is None:
            children = self.children()
            if crash:
                self.process.kill()
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            # Pipe EOF normally stops both children; confirm instead of silently
            # launching a second writer while a previous lock might remain.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                live = []
                for pid in children.values():
                    status = pathlib.Path(f"/proc/{pid}/status")
                    try:
                        if "\nState:\tZ" not in "\n" + status.read_text():
                            live.append(pid)
                    except FileNotFoundError:
                        pass
                if not live:
                    for pid in children.values():
                        try:
                            os.waitpid(pid, os.WNOHANG)
                        except ChildProcessError:
                            pass
                    break
                time.sleep(0.02)
            else:
                raise RuntimeError(f"Native children did not exit: {live}")
            self.process.stdout.close()
        if self.log:
            self.log.close()
            self.log = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
