"use strict";

const $ = (id) => document.getElementById(id);

const questionEl = $("question");
const askBtn = $("ask-btn");
const errorEl = $("error");
const advisorsEl = $("advisors");
const advisorGrid = $("advisor-grid");
const verdictEl = $("verdict");
const verdictBody = $("verdict-body");

let verdictText = "";

askBtn.addEventListener("click", convene);
questionEl.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") convene();
});

async function convene() {
  const question = questionEl.value.trim();
  if (!question) {
    showError("Enter a question for the council first.");
    return;
  }

  hideError();
  setBusy(true);
  resetOutput();

  try {
    const res = await fetch("/api/council", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`Server responded with ${res.status}`);
    }
    await readStream(res.body.getReader());
  } catch (err) {
    showError(err.message || "Something went wrong.");
  } finally {
    setBusy(false);
    verdictBody.classList.remove("cursor");
  }
}

async function readStream(reader) {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evt = parseEvent(raw);
      if (evt) handleEvent(evt);
    }
  }
}

function parseEvent(raw) {
  let event = "message";
  const dataLines = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

function handleEvent({ event, data }) {
  switch (event) {
    case "advisor_start":
      addAdvisorCard(data);
      break;
    case "advisor_done":
      fillAdvisorCard(data);
      break;
    case "synthesis_start":
      verdictEl.hidden = false;
      verdictText = "";
      verdictBody.classList.add("cursor");
      break;
    case "synthesis_delta":
      verdictText += data.text;
      verdictBody.innerHTML = mdToHtml(verdictText);
      verdictBody.classList.add("cursor");
      break;
    case "done":
      verdictBody.classList.remove("cursor");
      break;
    case "error":
      showError(data.message);
      break;
  }
}

function addAdvisorCard({ key, name, tagline }) {
  advisorsEl.hidden = false;
  const card = document.createElement("div");
  card.className = "card";
  card.id = `card-${key}`;
  card.innerHTML = `
    <div class="card-head">
      <div class="card-name">${escapeHtml(name)}</div>
      <div class="card-tag">${escapeHtml(tagline)}</div>
    </div>
    <div class="card-body">
      <span class="thinking"><span></span><span></span><span></span></span>
    </div>`;
  advisorGrid.appendChild(card);
}

function fillAdvisorCard({ key, view }) {
  const card = $(`card-${key}`);
  if (!card) return;
  card.querySelector(".card-body").innerHTML = mdToHtml(view);
}

/* --- helpers --- */

function resetOutput() {
  advisorGrid.innerHTML = "";
  advisorsEl.hidden = true;
  verdictEl.hidden = true;
  verdictBody.innerHTML = "";
  verdictText = "";
}

function setBusy(busy) {
  askBtn.disabled = busy;
  askBtn.textContent = busy ? "Deliberating…" : "Convene the council";
}

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.hidden = false;
}

function hideError() {
  errorEl.hidden = true;
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Minimal, dependency-free markdown: headings, lists, bold/italic/code.
function mdToHtml(md) {
  const lines = md.split("\n");
  let html = "";
  let listType = null; // "ul" | "ol" | null

  const closeList = () => {
    if (listType) {
      html += `</${listType}>`;
      listType = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, "");
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);

    if (heading) {
      closeList();
      const level = Math.min(heading[1].length + 2, 4); // h3/h4
      html += `<h${level}>${inline(heading[2])}</h${level}>`;
    } else if (bullet) {
      if (listType !== "ul") {
        closeList();
        html += "<ul>";
        listType = "ul";
      }
      html += `<li>${inline(bullet[1])}</li>`;
    } else if (numbered) {
      if (listType !== "ol") {
        closeList();
        html += "<ol>";
        listType = "ol";
      }
      html += `<li>${inline(numbered[1])}</li>`;
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return html;
}

function inline(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}
