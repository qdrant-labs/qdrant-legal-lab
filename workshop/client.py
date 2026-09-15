"""How the runners reach the cluster, and the one file a participant edits.

`lab.py` sits at the top of the repository rather than inside this package,
because it is the only file a participant changes and everything in here is
fixed. It is loaded from its path on every call, so an edit lands in a running
app without a restart.
"""

import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

LAB = Path(__file__).resolve().parents[1] / "lab.py"


def connect(write=False):
    load_dotenv(".env")
    url = os.getenv("QDRANT_URL")
    key = os.getenv("QDRANT_API_KEY") if write else (
        os.getenv("QDRANT_READONLY_API_KEY") or os.getenv("QDRANT_API_KEY")
    )
    if not url or not key:
        sys.exit("Set QDRANT_URL and a Qdrant API key in .env")
    return QdrantClient(url=url, api_key=key, timeout=120, cloud_inference=True)


def collection():
    load_dotenv(".env")
    return os.getenv("QDRANT_COLLECTION", "legal_lab_v2")


def lab():
    """Read lab.py as it is on disk right now and return it as a module.

    Importing it once would show a participant the old score after they edited
    it, and teach them their change did nothing. That is the one feedback
    failure this workshop cannot afford.
    """
    spec = importlib.util.spec_from_file_location("lab", LAB)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # The importlib frames above the real error are noise, and a person
        # reading them in a bar concludes they broke the workshop, not the file.
        # RuntimeError, not SystemExit: the browser runs this inside a request
        # handler, and SystemExit escapes `except Exception` and drops the
        # connection with no body, which is the hang this message exists to stop.
        raise RuntimeError(f"lab.py raised: {type(exc).__name__}: {exc}") from None
    return module


def representations(qc, name):
    """Which named vectors lab.py asks for, against how many the collection has.

    Execution, never correctness. A name states the model and the text behind
    it, and nothing states whether it is any good on this corpus.
    """
    info = qc.get_collection(name)
    present = set(info.config.params.vectors or {}) | set(
        info.config.params.sparse_vectors or {}
    )
    # Whichever of the collection's vector names lab.py mentions, wherever it says them.
    used = {vector for vector in present if f'"{vector}"' in LAB.read_text()}
    return (f"lab.py queries {len(used)} of the {len(present)} representations this "
            f"collection carries ({', '.join(sorted(used))})")
