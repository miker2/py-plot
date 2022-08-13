import importlib


def install_and_import(module: str):
    try:
        i_mod = importlib.import_module(module)

    except ModuleNotFoundError:
        import os
        import sys
        is_conda = os.path.exists(os.path.join(sys.base_prefix, 'conda-meta'))
        import subprocess
        if is_conda:
            print(f"Installing {module}. Please wait...")
            subprocess.check_call(["conda", "install", "-y", module])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

        i_mod = importlib.import_module(module)

    return i_mod
