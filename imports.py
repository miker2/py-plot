import importlib

def _install_via_conda(module: str):
    import subprocess
    try:
        subprocess.check_call(["conda", "install", "-y", "-c", "conda-forge", module])
        return True
    except subprocess.CalledProcessError:
        print(f"  Failed to install {module} via conda.")
        return False

def _install_via_pip(module: str):
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", module])
        return True
    except subprocess.CalledProcessError:
        print(f"  Failed to install {module} via pip.")
        return False

def install_and_import(module: str):
    try:
        i_mod = importlib.import_module(module)

    except ModuleNotFoundError:
        import os
        import sys
        is_conda = os.path.exists(os.path.join(sys.base_prefix, 'conda-meta'))
        print(f"Installing {module}. Please wait...")

        install_fcn = []
        if is_conda:
            install_fcn.append(_install_via_conda)
        install_fcn.append(_install_via_pip)

        for install in install_fcn:
            if install(module):
                break;

        i_mod = importlib.import_module(module)

    return i_mod
