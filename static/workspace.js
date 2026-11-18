const el = (id) => document.getElementById(id);
let draft;
let requestId;

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Check the form and try again.");
  }
  return data;
}

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    el("question").value = button.dataset.example;
    el("question").focus();
    el("ask").requestSubmit();
  });
});

el("ask").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (el("search-button").disabled || el("submit-ticket").disabled) return;
  el("search-button").disabled = true;
  el("result").hidden = true;
  el("ticket").hidden = true;
  el("status").textContent = "Searching the knowledge base…";
  try {
    const result = await post("/api/ask", { question: el("question").value });
    el("result-title").textContent = result.status === "answered" ? "Suggested guidance" : "IT review suggested";
    el("answer").textContent = result.answer;
    el("elapsed").textContent = `${result.latency_ms} ms`;
    el("citation").hidden = !result.citation;
    if (result.citation) {
      el("citation").textContent = `${result.citation.title} · ${result.citation.section}`;
    }
    draft = result.ticket;
    requestId = crypto.randomUUID();
    el("open-ticket").disabled = false;
    el("result").hidden = false;
    el("status").textContent = "";
  } catch (error) {
    el("status").textContent = error.message;
  } finally {
    el("search-button").disabled = false;
  }
});

el("open-ticket").addEventListener("click", () => {
  if (el("ticket").hidden) {
    for (const field of ["title", "description", "queue"]) el(field).value = draft[field];
    el("ticket-status").textContent = "";
    el("submit-ticket").hidden = false;
    for (const field of ["title", "description", "queue"]) el(field).disabled = false;
    el("ticket").hidden = false;
  }
  el("title").focus();
});

el("ticket").addEventListener("submit", async (event) => {
  event.preventDefault();
  el("submit-ticket").disabled = true;
  const fields = ["title", "description", "queue"];
  fields.forEach((field) => { el(field).disabled = true; });
  el("ticket-status").textContent = "Submitting ticket…";
  try {
    const ticket = await post("/api/tickets", {
      title: el("title").value, description: el("description").value,
      queue: el("queue").value, request_id: requestId,
    });
    el("ticket-status").textContent = `Ticket ${ticket.id} is queued.`;
    el("open-ticket").disabled = true;
    el("submit-ticket").hidden = true;
  } catch (error) {
    el("ticket-status").textContent = error.message;
  } finally {
    fields.forEach((field) => { el(field).disabled = el("submit-ticket").hidden; });
    el("submit-ticket").disabled = false;
  }
});
