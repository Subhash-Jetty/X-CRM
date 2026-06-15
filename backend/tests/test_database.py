import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import build_engine_kwargs, is_sqlite_url


class DatabaseEngineConfigTests(unittest.TestCase):
    def test_postgres_disables_asyncpg_prepared_statement_caches(self):
        kwargs = build_engine_kwargs(
            "postgresql+asyncpg://user:pass@pooler.example.com:6543/postgres",
            debug=False,
        )

        self.assertEqual(kwargs["connect_args"]["statement_cache_size"], 0)
        self.assertEqual(
            kwargs["connect_args"]["prepared_statement_cache_size"],
            0,
        )
        self.assertTrue(kwargs["pool_pre_ping"])

    def test_sqlite_does_not_receive_asyncpg_options(self):
        kwargs = build_engine_kwargs("sqlite+aiosqlite:///./xeno.db", debug=True)

        self.assertEqual(kwargs, {"echo": True})
        self.assertTrue(is_sqlite_url("sqlite+aiosqlite:///./xeno.db"))


if __name__ == "__main__":
    unittest.main()
