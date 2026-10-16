/* Lightweight rich-text editor for lesson sections.

   Progressive enhancement only: the formset textarea stays in the DOM and keeps
   receiving the section body, so saving works exactly as before with or without
   this script. The editable region mirrors that textarea with the markup the
   server allowlist accepts (see learning/rich_text.py). */
(() => {
  const BLOCK_TAGS = ["P", "H3", "H4", "UL", "OL", "LI", "BLOCKQUOTE", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD", "CAPTION", "FIGURE", "FIGCAPTION", "HR"];
  // Mirrors ALLOWED_TAGS in learning/rich_text.py, so what you see here is what the server keeps.
  const ALLOWED = new Set([...BLOCK_TAGS, "A", "STRONG", "EM", "BR", "IMG"]);
  const RENAME = { B: "STRONG", I: "EM", DIV: "P" };
  const DROP = ["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "SVG", "NOSCRIPT", "TEMPLATE", "INPUT", "BUTTON", "SELECT"];
  const ALLOWED_ATTRIBUTES = {
    A: ["href", "title"],
    IMG: ["src", "alt", "width", "height"],
    TH: ["scope", "colspan", "rowspan"],
    TD: ["colspan", "rowspan"],
    OL: ["start"],
  };
  const SAFE_URL = /^(https?:|mailto:|\/|\.\/|\.\.\/|#)/i;

  const isBlock = (node) => BLOCK_TAGS.includes(node.tagName);

  function rename(element, tag) {
    const fresh = document.createElement(tag);
    [...element.attributes].forEach((attribute) => fresh.setAttribute(attribute.name, attribute.value));
    fresh.append(...element.childNodes);
    element.replaceWith(fresh);
    return fresh;
  }

  function stripUnsafe(element) {
    [...element.children].forEach((original) => {
      if (DROP.includes(original.tagName)) {
        original.remove();
        return;
      }
      const child = RENAME[original.tagName] ? rename(original, RENAME[original.tagName]) : original;
      if (!ALLOWED.has(child.tagName)) {
        stripUnsafe(child);
        child.replaceWith(...child.childNodes);
        return;
      }
      const allowed = ALLOWED_ATTRIBUTES[child.tagName] || [];
      [...child.attributes].forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const isSafeUrl = (name === "href" || name === "src") && SAFE_URL.test(attribute.value.trim());
        if (!allowed.includes(name) || ((name === "href" || name === "src") && !isSafeUrl)) child.removeAttribute(attribute.name);
      });
      stripUnsafe(child);
    });
  }

  /* Pasted text carries literal newlines, which HTML renders as a space. Turn them
     into the breaks the old plain-text sections showed, so wording keeps its shape. */
  function breakNewlines(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      if (!node.textContent.trim().includes("\n")) return;
      const fragment = document.createDocumentFragment();
      node.textContent.split("\n").forEach((part, index) => {
        if (index) fragment.append(document.createElement("BR"));
        if (part) fragment.append(document.createTextNode(part));
      });
      node.replaceWith(fragment);
    });
  }

  /* Chrome can leave text and <div> blocks directly in the editable region;
     paragraph-wrap the runs so the stored body is valid HTML. */
  function paragraphise(root) {
    [...root.childNodes].forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent.trim()) {
          node.remove();
          return;
        }
        const paragraph = document.createElement("P");
        node.replaceWith(paragraph);
        paragraph.append(node);
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        node.remove();
        return;
      }
      if (node.tagName === "DIV") node = rename(node, "P");
      if (!isBlock(node) && node.tagName !== "BR") {
        const paragraph = document.createElement("P");
        node.replaceWith(paragraph);
        paragraph.append(node);
      }
    });
  }

  /* Chrome can leave a list or table inside the paragraph it was created from, which
     the browser then re-parses into different markup. Split those runs so the stored
     body matches what the learner will actually see. */
  function hoistBlocks(root) {
    for (let pass = 0; pass < 10; pass += 1) {
      const boxes = [...root.querySelectorAll("p, h3, h4, blockquote, figcaption, caption")].filter((box) =>
        [...box.children].some((child) => isBlock(child))
      );
      if (!boxes.length) return;
      boxes.forEach((box) => {
        const pieces = [];
        let paragraph = null;
        [...box.childNodes].forEach((node) => {
          if (isBlock(node)) {
            pieces.push(node);
            paragraph = null;
            return;
          }
          if (!paragraph) {
            paragraph = document.createElement(box.tagName);
            pieces.push(paragraph);
          }
          paragraph.append(node);
        });
        pieces.forEach((piece) => {
          if (piece.tagName === box.tagName && !piece.textContent.trim() && !piece.querySelector("img")) return;
          box.before(piece);
        });
        box.remove();
      });
    }
  }

  function isSpacer(node) {
    return node.tagName === "P" && !node.textContent.trim() && !node.querySelector("img, table");
  }

  /* An empty item is what Enter leaves behind when the author steps out of a list;
     a learner should never be shown a bare number or bullet. */
  function dropEmptyListItems(root) {
    root.querySelectorAll("ol, ul").forEach((list) => {
      [...list.children].forEach((item) => {
        if (item.tagName === "LI" && !item.textContent.trim() && !item.querySelector("img, table")) item.remove();
      });
      if (!list.querySelector("li")) list.remove();
    });
  }

  /* Chrome starts a brand-new list for every block the author converts, so a list
     built a few lines at a time arrives as several lists that each restart at 1.
     Merge same-type neighbours — across the blank paragraph the browser leaves
     between them — so the learner sees one continuously numbered list. */
  function mergeAdjacentLists(root) {
    [...root.children].forEach((list) => {
      if (list.tagName !== "OL" && list.tagName !== "UL") return;
      let next = list.nextElementSibling;
      while (next) {
        if (next.tagName === list.tagName) {
          const absorbed = next;
          next = absorbed.nextElementSibling;
          list.append(...absorbed.childNodes);
          absorbed.remove();
          continue;
        }
        if (isSpacer(next) && next.nextElementSibling && next.nextElementSibling.tagName === list.tagName) {
          const gap = next;
          next = gap.nextElementSibling;
          gap.remove();
          continue;
        }
        break;
      }
    });
  }

  function serialise(editor) {
    const clone = editor.cloneNode(true);
    breakNewlines(clone);
    paragraphise(clone);
    hoistBlocks(clone);
    dropEmptyListItems(clone);
    mergeAdjacentLists(clone);
    stripUnsafe(clone);
    return clone.innerHTML.trim();
  }

  function selectionInside(editor) {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    return editor.contains(range.commonAncestorContainer) ? range : null;
  }

  function insertAtCaret(editor, node) {
    const range = selectionInside(editor);
    editor.focus();
    if (!range) {
      editor.append(node);
      return;
    }
    range.deleteContents();
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  /* Tables and figures are block-level, so they belong beside the paragraph the
     caret sits in — dropping them inside a <p> makes the browser split the markup. */
  function insertBlock(editor, node) {
    editor.focus();
    const range = selectionInside(editor);
    let top = range && range.startContainer;
    if (top && top.nodeType === Node.TEXT_NODE) top = top.parentNode;
    while (top && top.parentNode && top.parentNode !== editor) top = top.parentNode;
    if (!top || top === editor || !top.parentNode) {
      editor.append(node);
    } else if (!top.textContent.trim() && isBlock(top)) {
      top.replaceWith(node);
    } else {
      top.after(node);
    }
    const caret = document.createRange();
    caret.setStartAfter(node);
    caret.collapse(true);
    setSelection(caret);
  }

  function setSelection(range) {
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  /* Select a node's contents so the next keystroke replaces the placeholder text. */
  function selectForReplacement(node) {
    const range = document.createRange();
    range.selectNodeContents(node);
    setSelection(range);
  }

  /* Keeps the caret on a real cell so row/column tools know what to act on.
     A caret in the caption still counts as being inside that table. */
  function activeCell(editor) {
    const range = selectionInside(editor);
    if (!range) return null;
    let node = range.startContainer;
    if (node.nodeType === Node.TEXT_NODE) node = node.parentNode;
    const cell = node.closest("th, td");
    if (cell && editor.contains(cell)) return cell;
    const table = node.closest("table");
    if (!table || !editor.contains(table)) return null;
    return table.tBodies[0]?.rows[0]?.cells[0] || table.tHead?.rows[0]?.cells[0] || null;
  }

  function makeCell(tag, text) {
    const cell = document.createElement(tag);
    if (tag === "TH") cell.setAttribute("scope", "col");
    cell.append(document.createTextNode(text || ""));
    return cell;
  }

  function buildTable(caption) {
    const table = document.createElement("TABLE");
    const head = document.createElement("CAPTION");
    head.textContent = caption;
    table.append(head);
    const thead = document.createElement("THEAD");
    const headerRow = document.createElement("TR");
    headerRow.append(makeCell("TH", ""), makeCell("TH", ""));
    thead.append(headerRow);
    const tbody = document.createElement("TBODY");
    for (let row = 0; row < 2; row += 1) {
      const bodyRow = document.createElement("TR");
      bodyRow.append(makeCell("TD", ""), makeCell("TD", ""));
      tbody.append(bodyRow);
    }
    table.append(thead, tbody);
    return table;
  }

  function tableTools(editor, status, action) {
    const cell = activeCell(editor);
    if (!cell) {
      status.textContent = "Place the cursor in a table first.";
      return;
    }
    status.textContent = "";
    const table = cell.closest("table");
    const row = cell.closest("tr");
    const columnIndex = [...row.children].indexOf(cell);
    const tag = cell.tagName;
    if (action === "add-row") {
      const fresh = document.createElement("TR");
      [...row.children].forEach((sibling) => fresh.append(makeCell(sibling.tagName, "")));
      (tag === "TH" ? row.parentNode : table.tBodies[0] || row.parentNode).append(fresh);
    } else if (action === "add-column") {
      table.querySelectorAll("tr").forEach((target) => {
        const heading = target.querySelector("th");
        target.append(makeCell(heading ? "TH" : "TD", ""));
      });
    } else if (action === "remove-row") {
      const body = row.closest("tbody") || row.closest("thead");
      if (body.rows.length > 1) row.remove();
    } else if (action === "remove-column") {
      if (table.rows.length && table.querySelector("tr").children.length > 1) {
        table.querySelectorAll("tr").forEach((target) => target.children[Math.min(columnIndex, target.children.length - 1)]?.remove());
      }
    }
    sync(editor);
  }

  function applyFormat(editor, value) {
    editor.focus();
    if (!selectionInside(editor)) {
      const range = document.createRange();
      range.selectNodeContents(editor.lastElementChild || editor);
      range.collapse(false);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    document.execCommand("formatBlock", false, `<${value}>`);
    sync(editor);
  }

  function sync(editor) {
    editor.dispatchEvent(new CustomEvent("au-editor:sync"));
  }

  function button(label, action, title) {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "au-editor-tool";
    node.dataset.action = action;
    node.textContent = label;
    node.setAttribute("aria-label", title || label);
    node.title = title || label;
    return node;
  }

  /* Real editors turn "- ", "1. ", "> " or "### " at the start of a line into the
     block it names, so the numbering a learner sees comes from the page rather
     than digits the author typed — and those digits cannot drift out of step. */
  function applyInputRule(editor, event) {
    const range = selectionInside(editor);
    if (!range || !range.collapsed || range.startContainer.nodeType !== Node.TEXT_NODE) return;
    const block = range.startContainer.parentElement?.closest("p, h3, h4");
    if (!block || !editor.contains(block)) return;
    const marker = range.startContainer.textContent.slice(0, range.startOffset);
    if (!marker || !block.textContent.startsWith(marker)) return;
    const lists = { "-": "UL", "*": "UL" };
    const heading = marker === "###" ? "H3" : marker === "####" ? "H4" : "";
    const tag = lists[marker] || (marker === "1." ? "OL" : marker === ">" ? "BLOCKQUOTE" : heading);
    if (!tag) return;
    event.preventDefault();
    const rest = range.startContainer.textContent.slice(range.startOffset);
    if (tag === "UL" || tag === "OL") {
      const item = document.createElement("LI");
      if (rest.trim()) item.append(document.createTextNode(rest.replace(/^\s+/, "")));
      const list = document.createElement(tag);
      list.append(item);
      block.replaceWith(list);
      selectForReplacement(item);
    } else {
      if (rest) range.startContainer.textContent = rest.replace(/^\s+/, "");
      else range.startContainer.textContent = "";
      rename(block, tag);
    }
    sync(editor);
  }

  function buildEditor(textarea) {
    const host = textarea.closest(".au-rich-field") || textarea.parentElement;
    if (host.dataset.editorReady) return;
    host.dataset.editorReady = "true";

    const bar = document.createElement("div");
    bar.className = "au-editor-bar";
    const format = document.createElement("select");
    format.className = "au-editor-format";
    format.setAttribute("aria-label", "Paragraph style");
    [["p", "Paragraph"], ["h3", "Heading 3"], ["h4", "Heading 4"], ["blockquote", "Quote"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      format.append(option);
    });
    bar.append(
      format,
      button("• List", "insertUnorderedList"),
      button("1. List", "insertOrderedList"),
      button("Link", "link"),
      button("Unlink", "unlink"),
      button("Table", "table"),
      button("Row +", "add-row", "Add table row"),
      button("Row −", "remove-row", "Remove table row"),
      button("Col +", "add-column", "Add table column"),
      button("Col −", "remove-column", "Remove table column"),
      button("Image", "image"),
    );

    const editor = document.createElement("div");
    editor.className = "au-editor";
    editor.contentEditable = "true";
    editor.setAttribute("role", "textbox");
    editor.setAttribute("aria-multiline", "true");
    editor.setAttribute("aria-label", textarea.previousElementSibling?.textContent.trim() || "Section content");
    editor.innerHTML = textarea.value;

    const status = document.createElement("p");
    status.className = "au-editor-status";
    status.setAttribute("role", "status");

    host.append(bar, editor, status);
    textarea.hidden = true;
    host.classList.add("is-enhanced");

    editor.addEventListener("au-editor:sync", () => {
      textarea.value = serialise(editor);
    });
    editor.addEventListener("input", () => sync(editor));
    editor.addEventListener("blur", () => sync(editor));
    editor.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = (event.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
      sync(editor);
    });
    editor.addEventListener("keydown", (event) => {
      if (event.key === " " && !event.ctrlKey && !event.metaKey && !event.altKey) {
        applyInputRule(editor, event);
        return;
      }
      if (event.key !== "Tab") return;
      const cell = activeCell(editor);
      const item = window.getSelection()?.anchorNode?.parentElement?.closest("li");
      if (!cell && !item) return;
      event.preventDefault();
      document.execCommand(event.shiftKey ? "outdent" : "indent");
      sync(editor);
    });
    host.closest("form")?.addEventListener("submit", () => sync(editor));

    format.addEventListener("change", () => {
      applyFormat(editor, format.value);
      format.value = "p";
    });

    // Toolbar buttons must not steal the editor selection before a list or
    // inline command is applied. Keeping the selection also makes multi-line
    // ordered and unordered lists behave consistently across browsers.
    bar.addEventListener("mousedown", (event) => {
      if (event.target.closest("[data-action]")) event.preventDefault();
    });

    bar.addEventListener("click", (event) => {
      const tool = event.target.closest("[data-action]");
      if (!tool) return;
      const action = tool.dataset.action;
      editor.focus();
      if (["add-row", "remove-row", "add-column", "remove-column"].includes(action)) {
        tableTools(editor, status, action);
        return;
      }
      if (action === "table") {
        const table = buildTable("Table title");
        insertBlock(editor, table);
        selectForReplacement(table.querySelector("caption"));
        sync(editor);
        return;
      }
      if (action === "image") {
        pickImage(editor, host, status);
        return;
      }
      if (action === "link") {
        createLink(editor, status);
        return;
      }
      document.execCommand(action);
      sync(editor);
    });
  }

  function createLink(editor, status) {
    const url = window.prompt("Link address", "https://");
    if (!url) return;
    status.textContent = "";
    if (!SAFE_URL.test(url.trim())) {
      status.textContent = "Links must start with https://, mailto: or /";
      return;
    }
    const range = selectionInside(editor);
    if (!range || range.collapsed) {
      const anchor = document.createElement("A");
      anchor.textContent = url.trim();
      anchor.setAttribute("href", url.trim());
      insertAtCaret(editor, anchor);
    } else {
      document.execCommand("createLink", false, url.trim());
    }
    status.textContent = "";
    sync(editor);
  }

  function pickImage(editor, host, status) {
    const uploadUrl = host.dataset.uploadUrl;
    if (!uploadUrl) {
      status.textContent = "Image uploads are not available for this lesson.";
      return;
    }
    const description = (window.prompt("Describe this image for learners. It becomes the caption and the alternative text.") || "").trim().slice(0, 180);
    if (!description) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp,image/gif";
    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      status.textContent = "Uploading image…";
      const payload = new FormData();
      payload.append("file", file);
      payload.append("alt", description);
      const token = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value;
      try {
        const response = await fetch(uploadUrl, { method: "POST", body: payload, headers: token ? { "X-CSRFToken": token } : {} });
        const data = await response.json();
        if (!response.ok || !data.url) {
          status.textContent = data.error || "That image could not be uploaded.";
          return;
        }
        const figure = document.createElement("FIGURE");
        const image = document.createElement("IMG");
        image.src = data.url;
        image.alt = data.alt || description;
        if (data.width) image.width = data.width;
        if (data.height) image.height = data.height;
        const caption = document.createElement("FIGCAPTION");
        caption.textContent = data.alt || description;
        figure.append(image, caption);
        insertBlock(editor, figure);
        status.textContent = "";
        sync(editor);
      } catch (error) {
        status.textContent = "That image could not be uploaded.";
      }
    });
    input.click();
  }

  document.addEventListener("DOMContentLoaded", () => {
    try {
      document.execCommand("defaultParagraphSeparator", false, "p");
    } catch (error) {
      /* Older engines keep their own paragraph behaviour; serialise() fixes the output. */
    }
    const selectors = ["textarea[id^='id_form-'][id$='-body']", "textarea#id_concept_body", "textarea#id_example_body", "textarea#id_notice_body"];
    document.querySelectorAll(selectors.join(", ")).forEach(buildEditor);
  });
})();
