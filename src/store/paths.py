from pathlib import Path

from src.utils import ensure_dir


class OutputPaths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifests = root / "manifests"
        self.ingest = root / "ingest"
        self.raw = root / "raw"
        self.raw_index = self.raw / "index"
        self.standard = root / "standard"
        self.linked = root / "linked"
        self.features = root / "features"
        self.models = root / "models"
        self.plots = root / "plots"
        self.reports = root / "reports"
        self.events = root / "events"

    def ensure(self) -> None:
        for path in [
            self.root,
            self.manifests,
            self.ingest,
            self.raw,
            self.raw_index,
            self.standard,
            self.linked,
            self.features,
            self.models,
            self.plots,
            self.reports,
            self.events,
        ]:
            ensure_dir(path)
