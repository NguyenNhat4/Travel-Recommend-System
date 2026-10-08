"""pgbouncer-setup.sh sinh userlist/ini đúng và từ chối đầu vào nguy hiểm. Chạy: python3 .../test_pgbouncer_setup.py"""
import pathlib
import subprocess
import tempfile
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
SETUP, INI = D / "pgbouncer-setup.sh", D / "pgbouncer.ini"

GOOD = """PGBOUNCER_UPSTREAM_HOST=db.vota.internal
DATABASE_URL=postgresql://vota_app_login:s3cret@127.0.0.1:6432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:other1@127.0.0.1:6432/vota
LEADER_LOCK_DATABASE_URL=postgresql://vota_app_login:s3cret@db.vota.internal:5432/vota
"""


def run(env_text: str):
    with tempfile.TemporaryDirectory() as tmp:
        env = pathlib.Path(tmp, "backend.env")
        env.write_text(env_text)
        out = pathlib.Path(tmp, "pgb")
        proc = subprocess.run(["bash", str(SETUP), str(env), str(out), str(INI), str(__import__("os").getuid())],
                              capture_output=True, text=True)
        files = {p.name: p.read_text() for p in out.glob("*")} if out.exists() else {}
        modes = {p.name: oct(p.stat().st_mode & 0o777) for p in out.glob("*")} if out.exists() else {}
        return proc, files, modes


class Setup(unittest.TestCase):
    def test_generates_userlist_and_ini(self):
        proc, files, modes = run(GOOD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(files["userlist.txt"], '"vota_app_login" "s3cret"\n"cdp_client_login" "other1"\n')
        self.assertIn("host=db.vota.internal port=5432 dbname=vota", files["pgbouncer.ini"])
        self.assertNotIn("__UPSTREAM_HOST__", files["pgbouncer.ini"])
        self.assertEqual(modes["userlist.txt"], "0o600")          # mật khẩu không đọc được bởi user khác

    def test_does_not_print_passwords(self):
        proc, _, _ = run(GOOD)
        self.assertNotIn("s3cret", proc.stdout + proc.stderr)

    def test_same_role_is_listed_once(self):
        text = GOOD.replace("cdp_client_login:other1", "vota_app_login:s3cret")
        _, files, _ = run(text)
        self.assertEqual(files["userlist.txt"].count("vota_app_login"), 1)

    def test_rejects_loopback_upstream(self):
        proc, _, _ = run(GOOD.replace("db.vota.internal", "127.0.0.1", 1))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("loopback", proc.stderr)

    def test_rejects_missing_upstream(self):
        proc, _, _ = run(GOOD.replace("PGBOUNCER_UPSTREAM_HOST=db.vota.internal\n", ""))
        self.assertNotEqual(proc.returncode, 0)

    def test_rejects_password_needing_url_encoding(self):
        proc, _, _ = run(GOOD.replace("s3cret", "p%40ss", 1))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("mã hoá URL", proc.stderr)

    def test_rejects_missing_database_url(self):
        proc, _, _ = run(GOOD.replace("DATABASE_URL=postgresql://vota_app_login:s3cret@127.0.0.1:6432/vota\n", "", 1))
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
