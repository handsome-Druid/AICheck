import asyncio
import subprocess
import sys
try:
    from src.controllers.vllm_test_controller import run
except ImportError:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
    from src.controllers.vllm_test_controller import run


if __name__ == "__main__":
    asyncio.run(run())
    if "--nopause" not in sys.argv:
        subprocess.run("pause", shell=True)