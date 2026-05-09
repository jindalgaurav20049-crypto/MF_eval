import os

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/fundlens_test.db")
os.environ.setdefault("AUTO_SYNC_MF_UNIVERSE", "false")
