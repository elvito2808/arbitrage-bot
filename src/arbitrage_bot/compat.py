"""Load relocated legacy modules under their original import names."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_PACKAGE_ROOT=Path(__file__).resolve().parent

def load_legacy_module(module_name: str, relative_path: str):
    target=(_PACKAGE_ROOT/relative_path).resolve()
    existing=sys.modules.get(module_name)
    if existing is not None:
        existing_file=getattr(existing,"__file__",None)
        if existing_file:
            try:
                if Path(existing_file).resolve()==target:
                    return existing
            except OSError:
                pass
    spec=spec_from_file_location(module_name,target)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load relocated module {module_name!r} from {target}")
    module=module_from_spec(spec)
    sys.modules[module_name]=module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name,None)
        raise
    return module
