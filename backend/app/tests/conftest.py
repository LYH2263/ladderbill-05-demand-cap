import os
import tempfile

# Point the app at an isolated throwaway DB before any app.* import.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ladderbill_test_"))
