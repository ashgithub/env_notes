const state = {
  tree: null,
  selected: null,
  page: null,
  activeNote: null,
  clipboard: null,
  saveTimer: null,
  searchTimer: null,
  highlightBlockId: null,
};

const treeEl = document.querySelector("#tree");
const canvas = document.querySelector("#canvas");
const emptyState = document.querySelector("#emptyState");
const pageTitle = document.querySelector("#pageTitle");
const breadcrumb = document.querySelector("#breadcrumb");
const saveStatus = document.querySelector("#saveStatus");
const contextMenu = document.querySelector("#contextMenu");
const searchInput = document.querySelector("#searchInput");
const searchBtn = document.querySelector("#searchBtn");
const searchResults = document.querySelector("#searchResults");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

function setStatus(text) {
  saveStatus.textContent = text;
}

async function loadTree() {
  state.tree = await api("/api/tree");
  renderTree();
  if (!state.selected) {
    const first = firstPage();
    if (first) {
      await selectPage(first);
    }
  }
}

function firstPage() {
  for (const notebook of state.tree.notebooks) {
    for (const section of notebook.sections) {
      if (section.pages[0]) {
        return {notebook, section, pagePath: section.pages[0].path, page: section.pages[0]};
      }
    }
  }
  return null;
}

function renderTree() {
  treeEl.innerHTML = "";
  for (const notebook of state.tree.notebooks) {
    treeEl.append(treeItem("N", notebook.title, {kind: "notebook", notebook}));
    const notebookChildren = el("div", "tree-children");
    for (const section of notebook.sections) {
      notebookChildren.append(treeItem("S", section.title, {kind: "section", notebook, section}));
      const sectionChildren = el("div", "tree-children");
      renderPages(sectionChildren, notebook, section, section.pages, "");
      notebookChildren.append(sectionChildren);
    }
    treeEl.append(notebookChildren);
  }
}

function renderPages(parent, notebook, section, pages, prefix) {
  for (const page of pages) {
    const pagePath = prefix ? `${prefix}/${page.path}` : page.path;
    parent.append(treeItem("P", page.title, {kind: "page", notebook, section, page, pagePath}));
    if (page.subpages.length) {
      const children = el("div", "tree-children");
      renderPages(children, notebook, section, page.subpages, pagePath);
      parent.append(children);
    }
  }
}

function treeItem(kindLabel, label, data) {
  const item = el("div", "tree-item");
  item.dataset.kind = data.kind;
  item.innerHTML = `<span class="tree-kind">${kindLabel}</span><span class="tree-label"></span>`;
  item.querySelector(".tree-label").textContent = label;
  if (data.kind === "page" && state.selected && samePage(data)) {
    item.classList.add("active");
  }
  item.addEventListener("click", async () => {
    if (data.kind === "page") {
      await selectPage(data);
    }
  });
  item.addEventListener("contextmenu", event => {
    event.preventDefault();
    showSidebarMenu(event.clientX, event.clientY, data);
  });
  return item;
}

function samePage(data) {
  return state.selected.notebook.path === data.notebook.path
    && state.selected.section.path === data.section.path
    && state.selected.pagePath === data.pagePath;
}

async function selectPage(selection, options = {}) {
  await savePageNow();
  state.selected = selection;
  state.highlightBlockId = options.highlightBlockId || null;
  const params = new URLSearchParams({
    notebook: selection.notebook.path,
    section: selection.section.path,
    page_path: selection.pagePath,
  });
  state.page = await api(`/api/page?${params}`);
  pageTitle.textContent = state.page.title;
  breadcrumb.textContent = `${selection.notebook.title} / ${selection.section.title} / ${state.page.title}`;
  renderCanvas();
  renderTree();
  if (state.highlightBlockId) {
    scrollToHighlightedNote();
  }
}

function renderCanvas() {
  canvas.innerHTML = "";
  emptyState.hidden = Boolean(state.page);
  if (!state.page) {
    return;
  }
  for (const block of state.page.blocks) {
    canvas.append(renderNote(block));
  }
}

function renderNote(block) {
  const note = el("article", "note");
  note.dataset.id = block.id;
  if (state.highlightBlockId === block.id) {
    note.classList.add("search-hit");
  }
  note.style.left = `${block.x}px`;
  note.style.top = `${block.y}px`;
  note.style.width = `${block.width}px`;
  note.style.height = `${block.height}px`;
  note.style.zIndex = block.z;
  note.innerHTML = `
    <div class="note-handle"><span>Note</span><span>${block.id.slice(-4)}</span></div>
    <div class="note-body" contenteditable="true"></div>
    <div class="note-resize"></div>
  `;
  note.querySelector(".note-body").innerHTML = block.content || "";

  note.addEventListener("mousedown", () => activateNote(note));
  note.addEventListener("contextmenu", event => {
    event.preventDefault();
    activateNote(note);
    showNoteMenu(event.clientX, event.clientY, note);
  });
  const body = note.querySelector(".note-body");
  body.addEventListener("input", () => scheduleSave());
  body.addEventListener("keydown", handleEditorKeydown);
  wireDrag(note, note.querySelector(".note-handle"));
  wireResize(note, note.querySelector(".note-resize"));
  return note;
}

function scrollToHighlightedNote() {
  requestAnimationFrame(() => {
    const note = document.querySelector(`.note[data-id="${CSS.escape(state.highlightBlockId)}"]`);
    if (!note) {
      return;
    }
    activateNote(note);
    note.scrollIntoView({block: "center", inline: "center", behavior: "smooth"});
  });
}

function activateNote(note) {
  document.querySelectorAll(".note.active").forEach(item => item.classList.remove("active"));
  state.activeNote = note;
  note.classList.add("active");
}

function wireDrag(note, handle) {
  handle.addEventListener("mousedown", event => {
    event.preventDefault();
    activateNote(note);
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = note.offsetLeft;
    const startTop = note.offsetTop;

    function move(moveEvent) {
      note.style.left = `${Math.max(0, startLeft + moveEvent.clientX - startX)}px`;
      note.style.top = `${Math.max(0, startTop + moveEvent.clientY - startY)}px`;
    }

    function stop() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", stop);
      scheduleSave();
    }

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", stop);
  });
}

function wireResize(note, handle) {
  handle.addEventListener("mousedown", event => {
    event.preventDefault();
    activateNote(note);
    const startX = event.clientX;
    const startY = event.clientY;
    const startWidth = note.offsetWidth;
    const startHeight = note.offsetHeight;

    function move(moveEvent) {
      note.style.width = `${Math.max(180, startWidth + moveEvent.clientX - startX)}px`;
      note.style.height = `${Math.max(110, startHeight + moveEvent.clientY - startY)}px`;
    }

    function stop() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", stop);
      scheduleSave();
    }

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", stop);
  });
}

function collectBlocks() {
  return [...document.querySelectorAll(".note")].map(note => {
    const previous = state.page.blocks.find(block => block.id === note.dataset.id) || {};
    return {
      id: note.dataset.id,
      x: note.offsetLeft,
      y: note.offsetTop,
      width: note.offsetWidth,
      height: note.offsetHeight,
      z: Number(note.style.zIndex || previous.z || 1),
      file: previous.file,
      content: note.querySelector(".note-body").innerHTML,
    };
  });
}

function scheduleSave() {
  if (!state.page || !state.selected) {
    return;
  }
  setStatus("Saving...");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(savePageNow, 350);
}

async function savePageNow() {
  if (!state.page || !state.selected) {
    return;
  }
  clearTimeout(state.saveTimer);
  const blocks = collectBlocks();
  await api("/api/page", {
    method: "PUT",
    body: JSON.stringify({
      notebook: state.selected.notebook.path,
      section: state.selected.section.path,
      page_path: state.selected.pagePath,
      blocks,
    }),
  });
  state.page.blocks = blocks;
  setStatus("Saved");
}

async function addQuickNote() {
  if (!state.selected) {
    alert("Create or select a page first.");
    return;
  }
  await savePageNow();
  const block = await api("/api/blocks", {
    method: "POST",
    body: JSON.stringify({
      notebook: state.selected.notebook.path,
      section: state.selected.section.path,
      page_path: state.selected.pagePath,
    }),
  });
  state.page.blocks.push(block);
  const note = renderNote(block);
  canvas.append(note);
  activateNote(note);
  note.querySelector(".note-body").focus();
}

function showNoteMenu(x, y, note) {
  const actions = [
    ["Cut", () => cutNote(note)],
    ["Copy", () => copyNote(note)],
    ["Paste", () => pasteNote()],
    ["Duplicate", () => duplicateNote(note)],
    ["---"],
    ["Bring to front", () => changeZ(note, "front")],
    ["Send to back", () => changeZ(note, "back")],
    ["---"],
    ["Delete", () => deleteNote(note), "danger"],
  ];
  showMenu(x, y, actions);
}

function showSidebarMenu(x, y, data) {
  const actions = [];
  if (data.kind === "notebook") {
    actions.push(["New section", () => createSection(data.notebook)]);
    actions.push(["Rename", () => renameItem(data)]);
    actions.push(["Delete", () => deleteItem(data), "danger"]);
  }
  if (data.kind === "section") {
    actions.push(["New page", () => createPage(data)]);
    actions.push(["Rename", () => renameItem(data)]);
    actions.push(["Delete", () => deleteItem(data), "danger"]);
  }
  if (data.kind === "page") {
    actions.push(["New subpage", () => createPage(data, data.pagePath)]);
    actions.push(["Duplicate", () => duplicatePage(data)]);
    actions.push(["Move", () => movePage(data)]);
    actions.push(["Rename", () => renameItem(data)]);
    actions.push(["Delete", () => deleteItem(data), "danger"]);
  }
  showMenu(x, y, actions);
}

function showMenu(x, y, actions) {
  contextMenu.innerHTML = "";
  for (const action of actions) {
    if (action[0] === "---") {
      contextMenu.append(document.createElement("hr"));
      continue;
    }
    const button = document.createElement("button");
    button.textContent = action[0];
    if (action[2]) {
      button.classList.add(action[2]);
    }
    button.addEventListener("click", async () => {
      hideMenu();
      await action[1]();
    });
    contextMenu.append(button);
  }
  contextMenu.style.left = `${x}px`;
  contextMenu.style.top = `${y}px`;
  contextMenu.hidden = false;
}

function hideMenu() {
  contextMenu.hidden = true;
}

function copyNote(note) {
  state.clipboard = {
    content: note.querySelector(".note-body").innerHTML,
    width: note.offsetWidth,
    height: note.offsetHeight,
  };
}

function cutNote(note) {
  copyNote(note);
  deleteNote(note);
}

function pasteNote() {
  if (!state.clipboard || !state.page) {
    return;
  }
  const maxZ = Math.max(...state.page.blocks.map(block => block.z), 0) + 1;
  const block = {
    id: `note-${crypto.randomUUID().slice(0, 10)}`,
    x: 160,
    y: 140,
    width: state.clipboard.width,
    height: state.clipboard.height,
    z: maxZ,
    content: state.clipboard.content,
  };
  state.page.blocks.push(block);
  canvas.append(renderNote(block));
  scheduleSave();
}

function duplicateNote(note) {
  copyNote(note);
  pasteNote();
}

function deleteNote(note) {
  note.remove();
  state.page.blocks = state.page.blocks.filter(block => block.id !== note.dataset.id);
  scheduleSave();
}

function changeZ(note, direction) {
  const notes = [...document.querySelectorAll(".note")];
  const zValues = notes.map(item => Number(item.style.zIndex || 1));
  note.style.zIndex = direction === "front" ? Math.max(...zValues) + 1 : Math.min(...zValues) - 1;
  scheduleSave();
}

async function createSection(notebook) {
  const title = prompt("Section name");
  if (!title) {
    return;
  }
  await api(`/api/sections/${encodeURIComponent(notebook.path)}`, {
    method: "POST",
    body: JSON.stringify({title}),
  });
  await loadTree();
}

async function createPage(data, parentPage = null) {
  const title = prompt(parentPage ? "Subpage name" : "Page name");
  if (!title) {
    return;
  }
  await api("/api/pages", {
    method: "POST",
    body: JSON.stringify({
      notebook: data.notebook.path,
      section: data.section.path,
      title,
      parent_page: parentPage,
    }),
  });
  await loadTree();
}

async function renameItem(data) {
  const title = prompt("New name", data.page?.title || data.section?.title || data.notebook?.title);
  if (!title) {
    return;
  }
  await savePageNow();
  await api("/api/rename", {
    method: "POST",
    body: JSON.stringify({
      kind: data.kind,
      notebook: data.notebook.path,
      section: data.section?.path,
      page_path: data.pagePath,
      title,
    }),
  });
  state.selected = null;
  state.page = null;
  await loadTree();
}

async function deleteItem(data) {
  if (!confirm(`Delete ${data.page?.title || data.section?.title || data.notebook?.title}?`)) {
    return;
  }
  await api("/api/delete", {
    method: "POST",
    body: JSON.stringify({
      kind: data.kind,
      notebook: data.notebook.path,
      section: data.section?.path,
      page_path: data.pagePath,
    }),
  });
  state.selected = null;
  state.page = null;
  pageTitle.textContent = "Choose a page";
  breadcrumb.textContent = "No page selected";
  canvas.innerHTML = "";
  await loadTree();
}

async function duplicatePage(data) {
  await api("/api/duplicate-page", {
    method: "POST",
    body: JSON.stringify({
      notebook: data.notebook.path,
      section: data.section.path,
      page_path: data.pagePath,
    }),
  });
  await loadTree();
}

async function movePage(data) {
  const target = prompt("Move under page path, or leave blank to move to section root", "");
  if (target === null) {
    return;
  }
  await savePageNow();
  await api("/api/move-page", {
    method: "POST",
    body: JSON.stringify({
      notebook: data.notebook.path,
      section: data.section.path,
      page_path: data.pagePath,
      target_parent: target.trim() || null,
    }),
  });
  state.selected = null;
  state.page = null;
  await loadTree();
}

document.querySelector("#newNotebookBtn").addEventListener("click", async () => {
  const title = prompt("Notebook name");
  if (!title) {
    return;
  }
  await api("/api/notebooks", {
    method: "POST",
    body: JSON.stringify({title}),
  });
  await loadTree();
});

document.querySelector("#quickNoteBtn").addEventListener("click", addQuickNote);

document.querySelectorAll("[data-command]").forEach(button => {
  button.addEventListener("click", () => {
    document.execCommand(button.dataset.command, false);
    scheduleSave();
  });
});

document.querySelector("#linkBtn").addEventListener("click", () => {
  const url = prompt("Link URL");
  if (url) {
    document.execCommand("createLink", false, url);
    scheduleSave();
  }
});

searchBtn.addEventListener("click", runSearch);

searchInput.addEventListener("input", () => {
  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(runSearch, 250);
});

searchInput.addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch();
  }
  if (event.key === "Escape") {
    searchInput.value = "";
    renderSearchResults([]);
  }
});

async function runSearch() {
  const query = searchInput.value.trim();
  if (!query) {
    renderSearchResults([]);
    return;
  }
  if (query.length < 2) {
    searchResults.hidden = false;
    searchResults.innerHTML = `<div class="search-empty">Keep typing</div>`;
    return;
  }
  try {
    const params = new URLSearchParams({q: query});
    const payload = await api(`/api/search?${params}`);
    renderSearchResults(payload.results || [], query);
  } catch (error) {
    console.error(error);
    searchResults.hidden = false;
    searchResults.innerHTML = `<div class="search-empty">Search failed</div>`;
  }
}

function renderSearchResults(results, query = "") {
  searchResults.innerHTML = "";
  searchResults.hidden = !query && results.length === 0;
  if (!query) {
    return;
  }
  if (!results.length) {
    searchResults.innerHTML = `<div class="search-empty">No matches</div>`;
    return;
  }

  for (const result of results) {
    const button = el("button", "search-result");
    const location = el("span", "search-location");
    location.textContent = `${result.notebook} / ${result.section} / ${result.page}`;
    const snippet = el("span", "search-snippet");
    snippet.append(...highlightText(result.excerpt || result.page, query));
    button.append(location, snippet);
    button.addEventListener("click", async () => {
      await selectPage(
        {
          notebook: {title: result.notebook, path: result.notebookPath},
          section: {title: result.section, path: result.sectionPath},
          page: {title: result.page, path: result.pagePath.split("/").at(-1), subpages: []},
          pagePath: result.pagePath,
        },
        {highlightBlockId: result.blockId},
      );
    });
    searchResults.append(button);
  }
}

function highlightText(text, query) {
  const parts = [];
  const source = text || "";
  const lowerSource = source.toLowerCase();
  const lowerQuery = query.toLowerCase();
  let index = 0;
  let matchIndex = lowerSource.indexOf(lowerQuery, index);
  while (matchIndex >= 0) {
    if (matchIndex > index) {
      parts.push(document.createTextNode(source.slice(index, matchIndex)));
    }
    const mark = document.createElement("mark");
    mark.textContent = source.slice(matchIndex, matchIndex + query.length);
    parts.push(mark);
    index = matchIndex + query.length;
    matchIndex = lowerSource.indexOf(lowerQuery, index);
  }
  if (index < source.length) {
    parts.push(document.createTextNode(source.slice(index)));
  }
  return parts;
}

function handleEditorKeydown(event) {
  if (event.key !== "Tab") {
    return;
  }
  if (!closestListItem(window.getSelection()?.anchorNode, event.currentTarget)) {
    return;
  }

  event.preventDefault();
  document.execCommand(event.shiftKey ? "outdent" : "indent", false);
  scheduleSave();
}

function closestListItem(node, editor) {
  let current = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  while (current && current !== editor) {
    if (current.tagName === "LI") {
      return current;
    }
    current = current.parentElement;
  }
  return null;
}

document.addEventListener("click", event => {
  if (!contextMenu.contains(event.target)) {
    hideMenu();
  }
});

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  return node;
}

loadTree().catch(error => {
  console.error(error);
  setStatus("Error");
  alert(`Env Notes failed to load: ${error.message}`);
});
