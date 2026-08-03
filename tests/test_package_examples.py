import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_package import build  # noqa: E402


class PackageExampleTests(unittest.TestCase):
    def test_all_runtime_readme_commands_run_in_temporary_package(self):
        with tempfile.TemporaryDirectory() as directory:
            package = build(Path(directory) / "project-cybersyn")
            commands = [
                line.strip() for line in
                (package / "tools" / "README.md").read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("python ")
            ]
            self.assertGreaterEqual(len(commands), 7)
            environment = os.environ.copy()
            environment["PYTHONUTF8"] = "1"
            for command in commands:
                argv = shlex.split(command)
                result = subprocess.run(
                    [sys.executable, *argv[1:]], cwd=package,
                    env=environment, capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0,
                                 f"{command}\nstdout={result.stdout}\nstderr={result.stderr}")


if __name__ == "__main__":
    unittest.main()
