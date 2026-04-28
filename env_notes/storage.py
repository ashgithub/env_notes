from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_ROOT = ROOT / "data" / "notebooks"
DATA_ROOT = Path(os.environ.get("ENV_NOTES_DATA_ROOT", DEFAULT_DATA_ROOT)).expanduser()


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", value, flags=re.ASCII).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Untitled"


def unique_path(parent: Path, name: str) -> Path:
    base = slugify(name)
    candidate = parent / base
    index = 2
    while candidate.exists():
        candidate = parent / f"{base} {index}"
        index += 1
    return candidate


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    tmp_path.replace(path)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "dt", "dd", "h1", "h2", "h3", "pre"}:
            self.parts.append(" ")

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def html_to_text(content: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(content)
    return parser.text()


def excerpt(text: str, query: str, radius: int = 90) -> str:
    lowered = text.lower()
    index = lowered.find(query.lower())
    if index < 0:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(query) + radius)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


@dataclass(frozen=True)
class PageLocation:
    notebook: Path
    section: Path
    page: Path


class NotebookStore:
    def __init__(self, root: Path = DATA_ROOT) -> None:
        self.root = root

    def bootstrap(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if any(self.root.iterdir()):
            return

        notebook = self.root / "My Notebook"
        section = notebook / "Quick Notes"
        page = section / "Welcome"
        notes = page / "notes"
        notes.mkdir(parents=True, exist_ok=True)

        write_json(
            notebook / "notebook.json",
            {"id": make_id("notebook"), "title": "My Notebook", "sections": ["Quick Notes"]},
        )
        write_json(
            section / "section.json",
            {"id": make_id("section"), "title": "Quick Notes", "pages": ["Welcome"]},
        )
        note_id = "note-001"
        write_json(
            page / "page.json",
            {
                "id": make_id("page"),
                "title": "Welcome",
                "blocks": [
                    {
                        "id": note_id,
                        "x": 120,
                        "y": 100,
                        "width": 360,
                        "height": 220,
                        "z": 1,
                        "file": f"notes/{note_id}.html",
                    }
                ],
            },
        )
        write_text(
            notes / f"{note_id}.html",
            "<p>Welcome to Env Notes.</p><ol><li>Create a section.</li><li>Add pages and subpages.</li><li>Drop notes anywhere on the canvas.</li></ol>",
        )

    def tree(self) -> dict[str, Any]:
        self.bootstrap()
        notebooks = []
        for notebook_path in sorted(self.root.iterdir()):
            if not notebook_path.is_dir() or not (notebook_path / "notebook.json").exists():
                continue
            notebook_meta = read_json(notebook_path / "notebook.json")
            notebooks.append(
                {
                    "id": notebook_meta["id"],
                    "title": notebook_meta["title"],
                    "path": notebook_path.name,
                    "sections": self._sections(notebook_path),
                }
            )
        return {"notebooks": notebooks}

    def search(self, query: str, limit: int = 40) -> dict[str, Any]:
        self.bootstrap()
        needle = query.strip()
        if not needle:
            return {"query": query, "results": []}

        results: list[dict[str, Any]] = []
        lowered = needle.lower()

        for notebook_path in sorted(self.root.iterdir()):
            if not notebook_path.is_dir() or not (notebook_path / "notebook.json").exists():
                continue
            notebook_meta = read_json(notebook_path / "notebook.json")
            for section_path in sorted(notebook_path.iterdir()):
                if not section_path.is_dir() or not (section_path / "section.json").exists():
                    continue
                section_meta = read_json(section_path / "section.json")
                self._search_pages(
                    notebook_path,
                    notebook_meta,
                    section_path,
                    section_meta,
                    section_path,
                    needle,
                    lowered,
                    results,
                    limit,
                )
                if len(results) >= limit:
                    return {"query": query, "results": results}

        return {"query": query, "results": results}

    def _search_pages(
        self,
        notebook_path: Path,
        notebook_meta: dict[str, Any],
        section_path: Path,
        section_meta: dict[str, Any],
        parent: Path,
        needle: str,
        lowered: str,
        results: list[dict[str, Any]],
        limit: int,
    ) -> None:
        for page_path in sorted(parent.iterdir()):
            if len(results) >= limit:
                return
            if not page_path.is_dir() or not (page_path / "page.json").exists():
                continue

            page_meta = read_json(page_path / "page.json")
            relative_page = page_path.relative_to(section_path).as_posix()
            page_title = str(page_meta.get("title", page_path.name))
            title_match = lowered in page_title.lower()

            if title_match:
                results.append(
                    {
                        "kind": "page",
                        "notebook": notebook_meta["title"],
                        "notebookPath": notebook_path.name,
                        "section": section_meta["title"],
                        "sectionPath": section_path.name,
                        "page": page_title,
                        "pagePath": relative_page,
                        "blockId": None,
                        "excerpt": page_title,
                    }
                )
                if len(results) >= limit:
                    return

            for block in page_meta.get("blocks", []):
                if len(results) >= limit:
                    return
                content = read_text(page_path / block.get("file", ""))
                text = html_to_text(content)
                if lowered not in text.lower():
                    continue
                results.append(
                    {
                        "kind": "note",
                        "notebook": notebook_meta["title"],
                        "notebookPath": notebook_path.name,
                        "section": section_meta["title"],
                        "sectionPath": section_path.name,
                        "page": page_title,
                        "pagePath": relative_page,
                        "blockId": block.get("id"),
                        "excerpt": excerpt(text, needle),
                    }
                )

            self._search_pages(
                notebook_path,
                notebook_meta,
                section_path,
                section_meta,
                page_path,
                needle,
                lowered,
                results,
                limit,
            )

    def _sections(self, notebook_path: Path) -> list[dict[str, Any]]:
        sections = []
        for section_path in sorted(notebook_path.iterdir()):
            if not section_path.is_dir() or not (section_path / "section.json").exists():
                continue
            meta = read_json(section_path / "section.json")
            sections.append(
                {
                    "id": meta["id"],
                    "title": meta["title"],
                    "path": section_path.name,
                    "pages": self._pages(section_path),
                }
            )
        return sections

    def _pages(self, parent: Path) -> list[dict[str, Any]]:
        pages = []
        for page_path in sorted(parent.iterdir()):
            if not page_path.is_dir() or not (page_path / "page.json").exists():
                continue
            meta = read_json(page_path / "page.json")
            pages.append(
                {
                    "id": meta["id"],
                    "title": meta["title"],
                    "path": page_path.name,
                    "subpages": self._pages(page_path),
                }
            )
        return pages

    def get_page(self, notebook: str, section: str, page_path: str) -> dict[str, Any]:
        location = self._page_location(notebook, section, page_path)
        meta = read_json(location.page / "page.json")
        blocks = []
        for block in meta.get("blocks", []):
            content_file = location.page / block["file"]
            blocks.append({**block, "content": read_text(content_file)})
        return {
            "notebook": notebook,
            "section": section,
            "path": page_path,
            "id": meta["id"],
            "title": meta["title"],
            "blocks": blocks,
        }

    def create_notebook(self, title: str) -> dict[str, Any]:
        path = unique_path(self.root, title)
        path.mkdir(parents=True)
        meta = {"id": make_id("notebook"), "title": title.strip() or path.name, "sections": []}
        write_json(path / "notebook.json", meta)
        return {"id": meta["id"], "title": meta["title"], "path": path.name}

    def create_section(self, notebook: str, title: str) -> dict[str, Any]:
        notebook_path = self.root / notebook
        path = unique_path(notebook_path, title)
        path.mkdir(parents=True)
        meta = {"id": make_id("section"), "title": title.strip() or path.name, "pages": []}
        write_json(path / "section.json", meta)
        return {"id": meta["id"], "title": meta["title"], "path": path.name}

    def create_page(
        self,
        notebook: str,
        section: str,
        title: str,
        parent_page: str | None = None,
    ) -> dict[str, Any]:
        parent = self.root / notebook / section
        if parent_page:
            parent = parent / parent_page
        path = unique_path(parent, title)
        (path / "notes").mkdir(parents=True)
        meta = {"id": make_id("page"), "title": title.strip() or path.name, "blocks": []}
        write_json(path / "page.json", meta)
        return {"id": meta["id"], "title": meta["title"], "path": path.name}

    def update_page(self, notebook: str, section: str, page_path: str, blocks: list[dict[str, Any]]) -> None:
        location = self._page_location(notebook, section, page_path)
        meta = read_json(location.page / "page.json")
        clean_blocks = []
        for index, block in enumerate(blocks, start=1):
            block_id = block.get("id") or f"note-{index:03d}"
            filename = block.get("file") or f"notes/{block_id}.html"
            clean_blocks.append(
                {
                    "id": block_id,
                    "x": int(block.get("x", 80)),
                    "y": int(block.get("y", 80)),
                    "width": int(block.get("width", 320)),
                    "height": int(block.get("height", 180)),
                    "z": int(block.get("z", index)),
                    "file": filename,
                }
            )
            write_text(location.page / filename, str(block.get("content", "")))
        meta["blocks"] = clean_blocks
        write_json(location.page / "page.json", meta)

    def add_block(self, notebook: str, section: str, page_path: str) -> dict[str, Any]:
        location = self._page_location(notebook, section, page_path)
        meta = read_json(location.page / "page.json")
        block_id = make_id("note")
        filename = f"notes/{block_id}.html"
        z = max([int(block.get("z", 0)) for block in meta.get("blocks", [])] or [0]) + 1
        block = {
            "id": block_id,
            "x": 120,
            "y": 100,
            "width": 340,
            "height": 190,
            "z": z,
            "file": filename,
        }
        meta.setdefault("blocks", []).append(block)
        write_json(location.page / "page.json", meta)
        write_text(location.page / filename, "<p>New note</p>")
        return {**block, "content": "<p>New note</p>"}

    def rename_item(self, kind: str, notebook: str, section: str | None, page_path: str | None, title: str) -> dict[str, Any]:
        if kind == "notebook":
            path = self.root / notebook
            meta_path = path / "notebook.json"
            parent = self.root
        elif kind == "section" and section:
            path = self.root / notebook / section
            meta_path = path / "section.json"
            parent = self.root / notebook
        elif kind == "page" and section and page_path:
            path = self.root / notebook / section / page_path
            meta_path = path / "page.json"
            parent = path.parent
        else:
            raise ValueError("Invalid rename target")

        meta = read_json(meta_path)
        meta["title"] = title.strip() or meta["title"]
        new_path = unique_path(parent, meta["title"])
        if new_path != path:
            path.rename(new_path)
            meta_path = new_path / meta_path.name
        write_json(meta_path, meta)
        return {"title": meta["title"], "path": new_path.name}

    def delete_item(self, kind: str, notebook: str, section: str | None, page_path: str | None) -> None:
        if kind == "notebook":
            path = self.root / notebook
        elif kind == "section" and section:
            path = self.root / notebook / section
        elif kind == "page" and section and page_path:
            path = self.root / notebook / section / page_path
        else:
            raise ValueError("Invalid delete target")
        if path.exists():
            shutil.rmtree(path)

    def duplicate_page(self, notebook: str, section: str, page_path: str) -> dict[str, Any]:
        source = self.root / notebook / section / page_path
        meta = read_json(source / "page.json")
        target = unique_path(source.parent, f"{meta['title']} Copy")
        shutil.copytree(source, target)
        copied_meta = read_json(target / "page.json")
        copied_meta["id"] = make_id("page")
        copied_meta["title"] = f"{meta['title']} Copy"
        write_json(target / "page.json", copied_meta)
        return {"id": copied_meta["id"], "title": copied_meta["title"], "path": target.name}

    def move_page(self, notebook: str, section: str, page_path: str, target_parent: str | None) -> dict[str, Any]:
        section_path = self.root / notebook / section
        source = section_path / page_path
        if not (source / "page.json").exists():
            raise FileNotFoundError(page_path)
        if target_parent:
            target_parent_path = section_path / target_parent
        else:
            target_parent_path = section_path
        if not target_parent_path.resolve().is_relative_to(section_path.resolve()):
            raise ValueError("Invalid target")
        if source.resolve() == target_parent_path.resolve() or target_parent_path.resolve().is_relative_to(source.resolve()):
            raise ValueError("Cannot move a page into itself")
        target = unique_path(target_parent_path, source.name)
        source.rename(target)
        relative = target.relative_to(section_path).as_posix()
        meta = read_json(target / "page.json")
        return {"id": meta["id"], "title": meta["title"], "path": relative}

    def _page_location(self, notebook: str, section: str, page_path: str) -> PageLocation:
        notebook_path = self.root / notebook
        section_path = notebook_path / section
        page = section_path / page_path
        if not page.resolve().is_relative_to(section_path.resolve()):
            raise ValueError("Invalid page path")
        if not (page / "page.json").exists():
            raise FileNotFoundError(page_path)
        return PageLocation(notebook_path, section_path, page)
