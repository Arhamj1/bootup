"""Export selected Linux man pages to plain text for the demo knowledge base.

Source: the Linux man-pages project, as packaged by Ubuntu (packages `manpages`
and `manpages-dev`). Needs groff, so run it on Linux/macOS:

    apt-get download manpages manpages-dev && for f in *.deb; do dpkg-deb -x $f ex; done
    python tools/export_man_pages.py ex/usr/share/man

Output: data/raw/open/man/<topic>/<page>.txt, plus every page's copyright and
license lines in data/LICENSES/linux-man-pages.txt (outside data/raw, so the
license text is not indexed).
"""
import gzip
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "open" / "man"
LICENSE_FILE = ROOT / "data" / "LICENSES" / "linux-man-pages.txt"

PAGES = {
    "processes": ["fork.2", "execve.2", "wait.2", "_exit.2", "getpid.2", "clone.2",
                  "credentials.7", "getrlimit.2"],
    "scheduling": ["sched.7", "nice.2", "sched_yield.2", "sched_setscheduler.2"],
    "synchronization": ["pthreads.7", "pthread_create.3", "pthread_join.3", "sem_overview.7",
                        "sem_wait.3", "sem_post.3", "sem_init.3", "futex.7"],
    "ipc": ["pipe.2", "pipe.7", "fifo.7", "shm_overview.7", "mq_overview.7", "signal.7",
            "kill.2", "sigaction.2"],
    "memory": ["mmap.2", "brk.2", "mprotect.2", "malloc.3"],
    "file-systems": ["open.2", "read.2", "write.2", "close.2", "lseek.2", "dup.2", "stat.2",
                     "inode.7", "path_resolution.7", "link.2", "unlink.2"],
}
# Sections that add little for students and mostly add noise to keyword search.
DROP = {"LIBRARY", "STANDARDS", "HISTORY", "VERSIONS", "COLOPHON", "SEE ALSO",
        "ATTRIBUTES", "CONFORMING TO"}
HEADING = re.compile(r"^[A-Z][A-Z0-9 &/_-]{2,40}$")


def render(src: Path) -> str:
    troff = gzip.decompress(src.read_bytes())
    out = subprocess.run(
        ["groff", "-mandoc", "-Tascii", "-rcR=1", "-rHY=0", "-rLL=78n", "-P", "-cbou"],
        input=troff, capture_output=True, check=True)
    return out.stdout.decode("ascii", errors="ignore"), troff.decode("utf-8", errors="ignore")


def strip_and_filter(text: str) -> str:
    lines = text.splitlines()
    nonblank = [i for i, ln in enumerate(lines) if ln.strip()]
    lines = lines[nonblank[0] + 1: nonblank[-1]]          # running header and footer
    kept, keep = [], True
    for ln in lines:
        if HEADING.match(ln):
            keep = ln.strip() not in DROP
        if keep:
            kept.append(ln)
    return "\n".join(kept).strip() + "\n"


def license_lines(troff: str) -> list[str]:
    return [ln.lstrip('.\\" ').strip() for ln in troff.splitlines()
            if ln.startswith('.\\"') and ("Copyright" in ln or "SPDX-License-Identifier" in ln)]


def main(man_root: str) -> None:
    man_root = Path(man_root)
    notices = ["Demo knowledge base pages come from the Linux man-pages project",
               "(https://www.kernel.org/doc/man-pages/), Ubuntu packages manpages and manpages-dev.",
               "Rendered to plain text with groff; sections LIBRARY, STANDARDS, HISTORY, VERSIONS,",
               "COLOPHON, SEE ALSO and ATTRIBUTES were removed. Per-page copyright and license lines:", ""]
    for topic, pages in PAGES.items():
        (OUT / topic).mkdir(parents=True, exist_ok=True)
        for page in pages:
            src = man_root / f"man{page.rsplit('.', 1)[1]}" / f"{page}.gz"
            text, troff = render(src)
            (OUT / topic / f"{page}.txt").write_text(strip_and_filter(text))
            notices.append(f"{page}:")
            notices.extend(f"    {ln}" for ln in license_lines(troff) or ["(no notice found in source)"])
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text("\n".join(notices) + "\n")
    print(f"exported {sum(len(p) for p in PAGES.values())} pages to {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
