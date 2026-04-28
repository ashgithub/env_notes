from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from env_notes.storage import NotebookStore


ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = ROOT / "static"

app = FastAPI(title="Env Notes")
store = NotebookStore()


class TitlePayload(BaseModel):
    title: str


class CreatePagePayload(BaseModel):
    notebook: str
    section: str
    title: str
    parent_page: str | None = None


class BlockPayload(BaseModel):
    id: str | None = None
    x: int = 80
    y: int = 80
    width: int = 320
    height: int = 180
    z: int = 1
    file: str | None = None
    content: str = ""


class SavePagePayload(BaseModel):
    notebook: str
    section: str
    page_path: str
    blocks: list[BlockPayload]


class RenamePayload(BaseModel):
    kind: Literal["notebook", "section", "page"]
    notebook: str
    section: str | None = None
    page_path: str | None = None
    title: str


class DeletePayload(BaseModel):
    kind: Literal["notebook", "section", "page"]
    notebook: str
    section: str | None = None
    page_path: str | None = None


class DuplicatePagePayload(BaseModel):
    notebook: str
    section: str
    page_path: str


class MovePagePayload(BaseModel):
    notebook: str
    section: str
    page_path: str
    target_parent: str | None = None


@app.on_event("startup")
def startup() -> None:
    store.bootstrap()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.head("/")
def head_index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/api/tree")
def get_tree() -> dict:
    return store.tree()


@app.get("/api/search")
def search_notes(q: str = Query(..., min_length=1), limit: int = Query(40, ge=1, le=100)) -> dict:
    return store.search(q, limit)


@app.get("/api/page")
def get_page(
    notebook: str = Query(...),
    section: str = Query(...),
    page_path: str = Query(...),
) -> dict:
    try:
        return store.get_page(notebook, section, page_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Page not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/notebooks")
def create_notebook(payload: TitlePayload) -> dict:
    return store.create_notebook(payload.title)


@app.post("/api/sections/{notebook}")
def create_section(notebook: str, payload: TitlePayload) -> dict:
    return store.create_section(notebook, payload.title)


@app.post("/api/pages")
def create_page(payload: CreatePagePayload) -> dict:
    return store.create_page(
        payload.notebook,
        payload.section,
        payload.title,
        payload.parent_page,
    )


@app.put("/api/page")
def save_page(payload: SavePagePayload) -> dict:
    try:
        store.update_page(
            payload.notebook,
            payload.section,
            payload.page_path,
            [block.model_dump() for block in payload.blocks],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Page not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/blocks")
def add_block(payload: DuplicatePagePayload) -> dict:
    try:
        return store.add_block(payload.notebook, payload.section, payload.page_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Page not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rename")
def rename_item(payload: RenamePayload) -> dict:
    try:
        return store.rename_item(
            payload.kind,
            payload.notebook,
            payload.section,
            payload.page_path,
            payload.title,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/delete")
def delete_item(payload: DeletePayload) -> dict:
    try:
        store.delete_item(payload.kind, payload.notebook, payload.section, payload.page_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/duplicate-page")
def duplicate_page(payload: DuplicatePagePayload) -> dict:
    try:
        return store.duplicate_page(payload.notebook, payload.section, payload.page_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/move-page")
def move_page(payload: MovePagePayload) -> dict:
    try:
        return store.move_page(
            payload.notebook,
            payload.section,
            payload.page_path,
            payload.target_parent,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
