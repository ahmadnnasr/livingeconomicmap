from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import hashlib
import json

from .models import Publication, RenderedPublication


class PublicationArchive:
    """
    Immutable file-backed archive.

    PostgreSQL persistence can implement the same contract in production.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        publication: Publication,
        rendered: list[RenderedPublication],
    ) -> Path:
        publication_dir = self.root / publication.publication_id
        publication_dir.mkdir(exist_ok=False)

        payload = asdict(publication)
        payload_text = json.dumps(payload, indent=2, sort_keys=True)
        (publication_dir / "publication.json").write_text(payload_text + "\n")

        manifest = {
            "publication_hash": hashlib.sha256(
                payload_text.encode("utf-8")
            ).hexdigest(),
            "formats": {},
        }

        for item in rendered:
            extension = {"markdown": "md", "html": "html", "json": "json"}[item.format]
            filename = f"publication.{extension}"
            (publication_dir / filename).write_text(item.content)
            manifest["formats"][item.format] = {
                "filename": filename,
                "content_hash": item.content_hash,
            }

        (publication_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        return publication_dir

    def verify(self, publication_id: str) -> bool:
        directory = self.root / publication_id
        manifest = json.loads((directory / "manifest.json").read_text())
        publication_text = (directory / "publication.json").read_text().rstrip("\n")
        actual_publication_hash = hashlib.sha256(
            publication_text.encode("utf-8")
        ).hexdigest()
        if actual_publication_hash != manifest["publication_hash"]:
            return False

        for details in manifest["formats"].values():
            content = (directory / details["filename"]).read_text()
            if hashlib.sha256(content.encode("utf-8")).hexdigest() != details["content_hash"]:
                return False
        return True
