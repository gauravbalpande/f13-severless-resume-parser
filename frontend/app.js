// Set this to your deployed API Gateway URL (see DEPLOYMENT.md).
// Example: "https://abc123.execute-api.us-east-1.amazonaws.com/Prod"
const API_BASE_URL = "https://txuu9cdgt1.execute-api.us-east-1.amazonaws.com/Prod";

const candidatesLoadingEl = document.getElementById("candidates-loading");
const candidatesTableEl = document.getElementById("candidates-table");
const candidatesTbodyEl = document.getElementById("candidates-tbody");
const candidateDetailsEl = document.getElementById("candidate-details");
const downloadReportBtn = document.getElementById("download-report-btn");

let candidates = [];
let selectedCandidateId = null;

async function fetchCandidates() {
  candidatesLoadingEl.classList.remove("hidden");
  candidatesTableEl.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE_URL}/candidates`);
    if (!res.ok) {
      throw new Error(`Failed to load candidates: ${res.status}`);
    }
    const data = await res.json();
    candidates = data.items || [];
    renderCandidates();
  } catch (err) {
    candidatesLoadingEl.textContent = `Error: ${err.message}`;
  }
}

function renderCandidates() {
  candidatesTbodyEl.innerHTML = "";

  if (!candidates.length) {
    candidatesLoadingEl.textContent = "No candidates found yet. Upload resumes to the S3 bucket.";
    candidatesLoadingEl.classList.remove("hidden");
    candidatesTableEl.classList.add("hidden");
    return;
  }

  candidatesLoadingEl.classList.add("hidden");
  candidatesTableEl.classList.remove("hidden");

  candidates.forEach((c) => {
    const tr = document.createElement("tr");
    tr.classList.add("clickable-row");
    tr.addEventListener("click", () => onCandidateSelected(c.candidateId));

    const topMatch = (c.matches || [])[0];
    const topMatchLabel = topMatch ? `${topMatch.jobId} (${topMatch.score})` : "—";

    tr.innerHTML = `
      <td>${escapeHtml(c.name || "Unknown")}</td>
      <td>${escapeHtml(c.email || "—")}</td>
      <td>${c.total_experience_years ?? 0}</td>
      <td>${escapeHtml(topMatchLabel)}</td>
    `;
    candidatesTbodyEl.appendChild(tr);
  });
}

async function onCandidateSelected(candidateId) {
  selectedCandidateId = candidateId;
  downloadReportBtn.disabled = false;

  candidateDetailsEl.innerHTML = "<p>Loading candidate details...</p>";

  try {
    const res = await fetch(`${API_BASE_URL}/candidates/${candidateId}`);
    if (!res.ok) {
      throw new Error(`Failed to load candidate: ${res.status}`);
    }
    const cand = await res.json();
    renderCandidateDetails(cand);
  } catch (err) {
    candidateDetailsEl.innerHTML = `<p class="error">Error: ${escapeHtml(err.message)}</p>`;
  }
}

function renderCandidateDetails(cand) {
  const skills = (cand.skills || []).join(", ");
  const titles = (cand.titles || []).join("; ");
  const matches = cand.matches || [];

  const matchesHtml =
    matches.length === 0
      ? "<li>No job matches yet.</li>"
      : matches
          .map(
            (m) =>
              `<li><strong>${escapeHtml(m.jobId)}</strong> — score: ${m.score}</li>`
          )
          .join("");

  candidateDetailsEl.innerHTML = `
    <div class="detail-card">
      <h3>${escapeHtml(cand.name || "Unknown")}</h3>
      <p><strong>Email:</strong> ${escapeHtml(cand.email || "—")}</p>
      <p><strong>Total experience:</strong> ${
        cand.total_experience_years ?? 0
      } years</p>
      <p><strong>Skills:</strong> ${escapeHtml(skills || "—")}</p>
      <p><strong>Titles found:</strong> ${escapeHtml(titles || "—")}</p>
      <h4>Job Matches</h4>
      <ul>${matchesHtml}</ul>
    </div>
  `;
}

downloadReportBtn.addEventListener("click", async () => {
  if (!selectedCandidateId) return;
  try {
    const res = await fetch(
      `${API_BASE_URL}/candidates/${selectedCandidateId}/report`
    );
    if (!res.ok) {
      throw new Error(`Failed to download report: ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `candidate-${selectedCandidateId}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Error downloading report: ${err.message}`);
  }
});

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Initial load
fetchCandidates();

