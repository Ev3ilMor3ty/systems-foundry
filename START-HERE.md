# Systems Foundry — Linux x86-64 portable preview

1. Extract the entire package into a folder you own. Keep its subfolders together.
2. Install a Java 21+ runtime. On Ubuntu 24.04/Debian 13: `sudo apt install openjdk-21-jre`.
3. Open a terminal in this folder and run `bash start.sh`.
4. Open **http://127.0.0.1:8090** in a browser on the same computer.
5. Click **Optimize & dispatch**, then advance ticks or use **Auto run**. Press Ctrl+C in the terminal to stop.

The package was tested on Debian 13 x86-64. Its native files require glibc 2.38+ and libstdc++ exporting GLIBCXX_3.4.32; install your distribution's `libstdc++6` package if needed. Older Linux systems should build the included source locally. This is not a Windows executable package; Windows has a CI-tested source build in `source/docs/INSTALL.md`.

No Rust, C++ compiler, Maven, Node, account or API key is needed to run this package. The Java runtime is installed separately. The source build and test instructions are under `source/`; all committed code is included. Library notices are under `THIRD-PARTY-LICENSES/`.

Scenario data is created in `data/` at first launch. Reset appends an event; it does not delete history. Preserve your data directory when upgrading. Only one instance may own a data directory.

Use `bash start.sh --port 8091` for another port. The app remains a local fictional simulation, with no public-service authentication. Endurance evidence and its limits are in `source/docs/VALIDATION.md`.
