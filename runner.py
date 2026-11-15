"""Runner cadangan jika pytest tidak terpasang: python tests/runner.py"""
import sys, tempfile, pathlib, inspect, traceback
sys.path[:0] = ["src", "tests"]
import test_strategy, test_risk_sim, test_pipeline
fails = 0
for mod in (test_strategy, test_risk_sim, test_pipeline):
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("test_"):
            continue
        try:
            kw = {"tmp_path": pathlib.Path(tempfile.mkdtemp())} if "tmp_path" in inspect.signature(fn).parameters else {}
            
            if "monkeypatch" in inspect.signature(fn).parameters:
                import os
                class MP:
                    def setenv(self, k, v): os.environ[k] = v
                kw["monkeypatch"] = MP()
            fn(**kw); print("PASS", name)
        except Exception:
            fails += 1; print("FAIL", name); traceback.print_exc()
sys.exit(1 if fails else 0)
