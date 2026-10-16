"""Check the Docker COPY closure locally without Docker, pip or network."""
from pathlib import Path
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PackageTests(unittest.TestCase):
    def test_minimal_packaged_imports_catalogs_and_safe_help(self):
        lines = (ROOT / "experiments/weather_autonomy/Dockerfile.freshness-monitor").read_text().splitlines()
        self.assertIn('ENTRYPOINT ["python", "-m", "freshness_monitor"]', lines)
        self.assertIn('CMD ["--help"]', lines)
        with tempfile.TemporaryDirectory(prefix="icon2i-package-") as tmp:
            root = Path(tmp)
            work = root / "app/experiments/weather_autonomy"
            work.mkdir(parents=True)
            for line in lines:
                if not line.startswith("COPY "):
                    continue
                *sources, destination = shlex.split(line)[1:]
                target = root / destination.lstrip("/") if destination.startswith("/") else work / destination
                target.mkdir(parents=True, exist_ok=True)
                for source in sources:
                    path = ROOT / source
                    if path.is_dir():
                        shutil.copytree(path, target, dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                    else:
                        shutil.copyfile(path, target / path.name)
            code = ("import sys,socket;sys.path.insert(0,'.');"
                    "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden'));"
                    "from freshness_monitor.contracts import catalogs;"
                    "import freshness_monitor.__main__,freshness_monitor.dispatcher;"
                    "a,b=catalogs();assert len(a.istat_codes)==215;assert b['municipality_count']==7894;"
                    "print('packaged imports and pinned catalogs OK')")
            result = subprocess.run([sys.executable, "-B", "-I", "-c", code],
                                    cwd=work, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            result = subprocess.run([sys.executable, "-B", "-m", "freshness_monitor", "--help"],
                                    cwd=work, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn("--scheduled-slot", result.stdout)
            self.assertNotIn("--use-execution-slot", result.stdout)
            result = subprocess.run([sys.executable, "-B", "-m", "freshness_monitor.dispatcher", "--help"],
                                    cwd=work, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn("--serve", result.stdout)


if __name__ == "__main__":
    unittest.main()
