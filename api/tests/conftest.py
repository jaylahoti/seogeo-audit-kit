import os
import tempfile

# Tests use a throwaway database, never the real audits.db.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
