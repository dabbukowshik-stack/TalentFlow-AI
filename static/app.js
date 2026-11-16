let currentCandidates = [];
let allJobs = [];
let activeFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  loadJobs();
  loadMetrics();
});

// Fetch all jobs
async function loadJobs() {
  try {
    const res = await fetch('/api/jobs');
    allJobs = await res.json();
    const select = document.getElementById('jobSelect');
    select.innerHTML = '';
    
    allJobs.forEach(job => {
      const opt = document.createElement('option');
      opt.value = job.id;
      opt.textContent = `${job.title} (${job.location})`;
      select.appendChild(opt);
    });

    if (allJobs.length > 0) {
      updateJobBanner(allJobs[0]);
      loadCandidates();
    }
  } catch (err) {
    console.error('Failed to load jobs:', err);
  }
}

// Update header with current job criteria
function updateJobBanner(job) {
  document.getElementById('currentJobTitle').textContent = job.title;
  document.getElementById('currentJobSkills').textContent = `Required Skills: ${job.required_skills} | Min Exp: ${job.min_experience} yrs | Loc: ${job.location}`;
}

// Fetch candidates for selected job
async function loadCandidates() {
  const jobId = document.getElementById('jobSelect').value;
  const currentJob = allJobs.find(j => j.id == jobId);
  if (currentJob) updateJobBanner(currentJob);

  try {
    const res = await fetch(`/api/candidates?job_id=${jobId}`);
    currentCandidates = await res.json();
    renderKanban();
    loadMetrics();
  } catch (err) {
    console.error('Failed to load candidates:', err);
  }
}

// Refresh KPI cards
async function loadMetrics() {
  try {
    const res = await fetch('/api/metrics');
    const data = await res.json();
    document.getElementById('statTotalCandidates').textContent = data.total_candidates;
    document.getElementById('statActiveSequences').textContent = data.active_sequences;
    document.getElementById('statAvgScore').textContent = `${data.avg_match_score}%`;
  } catch (err) {
    console.error('Failed to fetch metrics:', err);
  }
}

// Render Kanban board columns
function renderKanban() {
  const stages = ['Sourced', 'Shortlisted', 'Interview', 'Client Review'];
  
  stages.forEach(stage => {
    const col = document.getElementById(`col-${stage}`);
    col.innerHTML = '';
  });

  const counts = { 'Sourced': 0, 'Shortlisted': 0, 'Interview': 0, 'Client Review': 0 };

  currentCandidates.forEach(cand => {
    // Check filters
    if (activeFilter === 'high' && cand.match_score < 80) return;
    if (activeFilter === 'seq' && cand.sequence_status !== 'Active Sequence' && cand.sequence_status !== 'Step 2 Dispatched') return;

    if (counts[cand.stage] !== undefined) counts[cand.stage]++;

    const card = document.createElement('div');
    card.className = 'candidate-card';
    card.draggable = true;
    card.id = `cand-${cand.id}`;
    card.ondragstart = (e) => drag(e, cand.id);

    // Score badge class
    let badgeClass = 'match-high';
    if (cand.match_score < 50) badgeClass = 'match-low';
    else if (cand.match_score < 80) badgeClass = 'match-med';

    card.innerHTML = `
      <div class="card-top">
        <span class="card-name">${escapeHtml(cand.name)}</span>
        <span class="match-badge ${badgeClass}" onclick="showScoreBreakdown(${cand.id})" title="Click to view AI Match Breakdown">
          ✨ ${cand.match_score}% Match
        </span>
      </div>
      <div class="card-headline">${escapeHtml(cand.headline || 'Candidate')}</div>
      <div class="card-meta">
        <span>📍 ${escapeHtml(cand.location || 'Remote')}</span>
        <span>⏱️ ${cand.experience_years} yrs exp</span>
      </div>
      <div class="sequence-indicator">
        <span>✉️ ${escapeHtml(cand.sequence_status)}</span>
      </div>
      <div class="card-actions">
        <small style="font-size:10px; color:#64748B;">${escapeHtml(cand.last_activity || 'Active')}</small>
        <button class="btn-xs" onclick="simulateCandidateReply(${cand.id})">Simulate Reply</button>
      </div>
    `;

    const targetCol = document.getElementById(`col-${cand.stage}`);
    if (targetCol) {
      targetCol.appendChild(card);
    }
  });

  stages.forEach(stage => {
    document.getElementById(`count-${stage}`).textContent = counts[stage] || 0;
  });
}

// Filter buttons
function filterByScore(type) {
  activeFilter = type;
  document.querySelectorAll('.chip-filter').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderKanban();
}

// Drag & Drop Kanban Handlers
function allowDrop(ev) {
  ev.preventDefault();
  ev.currentTarget.classList.add('drag-over');
}

function drag(ev, candId) {
  ev.dataTransfer.setData("text/plain", candId);
}

async function drop(ev, newStage) {
  ev.preventDefault();
  ev.currentTarget.classList.remove('drag-over');
  const candId = ev.dataTransfer.getData("text/plain");

  try {
    await fetch('/api/candidates/update-stage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candId, new_stage: newStage })
    });
    await loadCandidates();
  } catch (err) {
    console.error('Error updating stage:', err);
  }
}

// Real-time Duplicate Detection
async function checkDuplicate() {
  const email = document.getElementById('candEmail').value.trim();
  const name = document.getElementById('candName').value.trim();
  const alertBox = document.getElementById('duplicateAlert');

  if (!email && !name) {
    alertBox.style.display = 'none';
    return;
  }

  try {
    const res = await fetch('/api/candidates/check-duplicate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name })
    });
    const data = await res.json();
    if (data.is_duplicate) {
      alertBox.style.display = 'block';
      alertBox.innerHTML = `⚠️ <strong>Duplicate Warning:</strong> A record for <em>${escapeHtml(data.candidate.name)}</em> (${escapeHtml(data.candidate.email)}) already exists in your talent database.`;
    } else {
      alertBox.style.display = 'none';
    }
  } catch (err) {
    console.error(err);
  }
}

// 1-Click Candidate Sourcing Form Submit
async function handleCandidateSubmit(e) {
  e.preventDefault();
  const jobId = document.getElementById('jobSelect').value;
  const name = document.getElementById('candName').value;
  const email = document.getElementById('candEmail').value;
  const headline = document.getElementById('candHeadline').value;
  const experience_years = document.getElementById('candExp').value;
  const location = document.getElementById('candLoc').value;
  const skills = document.getElementById('candSkills').value;
  const auto_sequence = document.getElementById('autoSequence').checked;

  const btn = document.getElementById('btnImport');
  btn.textContent = 'Analyzing & Scoring...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/candidates/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: jobId,
        name,
        email,
        headline,
        experience_years,
        location,
        skills,
        auto_sequence
      })
    });
    const data = await res.json();

    closeModal('importModal');
    document.getElementById('importForm').reset();
    document.getElementById('duplicateAlert').style.display = 'none';
    await loadCandidates();
    
    // Automatically showcase score breakdown for newly imported candidate
    if (data.candidate_id) {
      showScoreBreakdown(data.candidate_id);
    }
  } catch (err) {
    alert('Failed to import candidate');
  } finally {
    btn.textContent = 'Import & Score Candidate';
    btn.disabled = false;
  }
}

// Show AI Score Breakdown Flyout
function showScoreBreakdown(candId) {
  const cand = currentCandidates.find(c => c.id === candId);
  if (!cand) return;

  const bd = cand.match_breakdown || { matched: [], missing: [] };
  const matchedPills = (bd.matched || []).map(s => `<span class="skill-pill matched">✓ ${escapeHtml(s)}</span>`).join('');
  const missingPills = (bd.missing || []).length > 0
    ? (bd.missing || []).map(s => `<span class="skill-pill missing">✕ ${escapeHtml(s)}</span>`).join('')
    : '<span style="font-size:12px; color:#10B981;">No required skills missing!</span>';

  let color = '#10B981';
  if (cand.match_score < 50) color = '#64748B';
  else if (cand.match_score < 80) color = '#F59E0B';

  const body = document.getElementById('scoreModalBody');
  body.innerHTML = `
    <div class="fit-summary">
      <div class="fit-circle" style="background:${color};">
        ${cand.match_score}%
      </div>
      <div>
        <h4>${escapeHtml(cand.name)}</h4>
        <p style="font-size:13px; color:#64748B;">${escapeHtml(cand.headline)} | ${escapeHtml(cand.location)}</p>
        <p style="font-size:12px; margin-top:4px;">Experience: <strong>${cand.experience_years} years</strong></p>
      </div>
    </div>

    <div style="margin-bottom:16px;">
      <h5 style="font-size:13px; font-weight:700;">Matched Core Competencies:</h5>
      <div class="skills-pill-group">${matchedPills || 'None matched'}</div>
    </div>

    <div style="margin-bottom:20px;">
      <h5 style="font-size:13px; font-weight:700;">Identified Skill Gaps:</h5>
      <div class="skills-pill-group">${missingPills}</div>
    </div>

    <div style="background:#F8FAFC; border:1px solid #E2E8F0; padding:12px; border-radius:6px; margin-bottom:16px;">
      <h5 style="font-size:12px; font-weight:700; margin-bottom:4px;">Outreach Automation Status:</h5>
      <p style="font-size:12px; color:#334155;">Status: <strong>${escapeHtml(cand.sequence_status)}</strong> (Step: ${cand.sequence_step})</p>
      <p style="font-size:11px; color:#64748B; margin-top:2px;">Last Audit Event: ${escapeHtml(cand.last_activity)}</p>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center;">
      <button class="btn btn-secondary" onclick="simulateSequenceNext(${cand.id})">Trigger Follow-Up Step 2</button>
      <button class="btn btn-primary" onclick="simulateCandidateReply(${cand.id})">Simulate Candidate Response</button>
    </div>
  `;

  openModal('scoreModal');
}

// Simulate sequence follow up
async function simulateSequenceNext(candId) {
  await fetch('/api/candidates/trigger-sequence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_id: candId, action: 'next_step' })
  });
  closeModal('scoreModal');
  await loadCandidates();
}

// Simulate candidate response (auto pauses sequence and moves to Shortlisted)
async function simulateCandidateReply(candId) {
  await fetch('/api/candidates/trigger-sequence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_id: candId, action: 'reply' })
  });
  closeModal('scoreModal');
  await loadCandidates();
}

// Create new Job Order
async function handleJobCreate(e) {
  e.preventDefault();
  const title = document.getElementById('jobTitleInput').value;
  const department = document.getElementById('jobDeptInput').value;
  const location = document.getElementById('jobLocInput').value;
  const min_experience = document.getElementById('jobExpInput').value;
  const required_skills = document.getElementById('jobSkillsInput').value;

  try {
    await fetch('/api/jobs/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, department, location, min_experience, required_skills })
    });
    closeModal('jobModal');
    await loadJobs();
  } catch (err) {
    alert('Failed to create job');
  }
}

// Modal Helpers
function openModal(id) {
  document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}

function openImportModal() { openModal('importModal'); }
function openJobModal() { openModal('jobModal'); }
function openPrdModal() { openModal('prdModal'); }

function openSimulationPanel() {
  alert("Sequence Simulator:\n- Sourced candidates automatically receive initial outreach emails.\n- Drag & drop candidates to 'Interview' or click 'Simulate Reply' to pause outreach and advance the candidate!");
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
  });
}
