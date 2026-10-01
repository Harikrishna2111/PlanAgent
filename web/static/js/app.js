/* ═══════════════════════════════════════════════════════════════════
   PlanAgent — Frontend Logic v2.5
   Premium interactive UI with animations, particles, gauges, and exports
   ═══════════════════════════════════════════════════════════════════ */

// ── Room Type Colors ─────────────────────────────────────────────
const ROOM_COLORS = {
    bedroom:     '#A8D8EA',
    bathroom:    '#B8E6C8',
    kitchen:     '#FFD3B6',
    living_room: '#FFAAA5',
    dining:      '#DCEDC1',
    entrance:    '#D5AAFF',
    hallway:     '#F0E68C',
    balcony:     '#C4FAF8',
    study:       '#F4C2C2',
    pooja:       '#FFE4B5',
    utility:     '#D3D3D3',
    garage:      '#C0C0C0',
    staircase:   '#E6E6FA',
    store:       '#DEB887',
};

// ── Room Type Icons ──────────────────────────────────────────────
const ROOM_ICONS = {
    bedroom:     '🛏️',
    bathroom:    '🚿',
    kitchen:     '🍳',
    living_room: '🛋️',
    dining:      '🍽️',
    entrance:    '🚪',
    hallway:     '🏠',
    balcony:     '🌿',
    study:       '📚',
    pooja:       '🕉️',
    utility:     '🔧',
    garage:      '🚗',
    staircase:   '🪜',
    store:       '📦',
};

// ── Example Prompts ──────────────────────────────────────────────
const EXAMPLES = [
    `Design a 2BHK house on a 40 × 60 ft plot with two bedrooms, two bathrooms, kitchen, living room and dining area. The kitchen should be near the dining area, bedrooms should be close to bathrooms, and the entrance should connect to the living room.`,
    `Design a 3BHK villa on a 50 × 70 ft plot with three bedrooms, three bathrooms, a large kitchen, living room, dining room, and study room. The master bedroom should be away from the entrance, kitchen near the dining room, and all bedrooms close to bathrooms.`,
    `Design a studio apartment on a 20 × 30 ft plot with one bedroom, one bathroom, a kitchen, and a living area. The kitchen should be near the living area, and the bathroom should be close to the bedroom.`,
    `Design an office layout on a 60 × 40 ft plot with three study rooms, one kitchen, two bathrooms, a large living room as reception, and an entrance. The entrance should connect to the living room, kitchen near the bathrooms, and study rooms should be away from the entrance.`,
];

// ── State ────────────────────────────────────────────────────────
let pipelineResult = null;

// ── Initialize ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initParticleCanvas();
    initNavScroll();
    initCharCount();
    initNavLinks();
    initMobileToggle();
    initTabIndicator();
    initInputValidation();
});

// ── Particle Canvas ─────────────────────────────────────────────
function initParticleCanvas() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    let animId;
    let w, h;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    function createParticles() {
        particles = [];
        const count = Math.floor((w * h) / 18000);
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * w,
                y: Math.random() * h,
                r: Math.random() * 1.5 + 0.3,
                dx: (Math.random() - 0.5) * 0.3,
                dy: (Math.random() - 0.5) * 0.3,
                alpha: Math.random() * 0.4 + 0.1,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        for (const p of particles) {
            p.x += p.dx;
            p.y += p.dy;

            if (p.x < 0) p.x = w;
            if (p.x > w) p.x = 0;
            if (p.y < 0) p.y = h;
            if (p.y > h) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(107, 138, 255, ${p.alpha})`;
            ctx.fill();
        }

        // Draw connections between nearby particles
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 100) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(107, 138, 255, ${0.04 * (1 - dist / 100)})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }

        animId = requestAnimationFrame(draw);
    }

    resize();
    createParticles();
    draw();

    window.addEventListener('resize', () => {
        resize();
        createParticles();
    });
}

// ── Nav Scroll Effect ───────────────────────────────────────────
function initNavScroll() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;

    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                navbar.classList.toggle('scrolled', window.scrollY > 40);
                ticking = false;
            });
            ticking = true;
        }
    });
}

// ── Mobile Nav Toggle ───────────────────────────────────────────
function initMobileToggle() {
    const toggle = document.getElementById('mobile-toggle');
    const links = document.getElementById('nav-links');
    if (!toggle || !links) return;

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = links.classList.toggle('mobile-open');
        toggle.setAttribute('aria-expanded', isOpen);
    });

    // Close on link click
    links.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            links.classList.remove('mobile-open');
            toggle.setAttribute('aria-expanded', 'false');
        });
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!links.contains(e.target) && !toggle.contains(e.target)) {
            links.classList.remove('mobile-open');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });
}

// ── Nav Active Link Tracking ────────────────────────────────────
function initNavLinks() {
    const links = document.querySelectorAll('.nav-link[data-section]');
    const sections = [];

    links.forEach(link => {
        const sectionId = link.dataset.section;
        const section = document.getElementById(sectionId);
        if (section) sections.push({ link, section });
    });

    if (sections.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                links.forEach(l => l.classList.remove('active'));
                const match = sections.find(s => s.section === entry.target);
                if (match) match.link.classList.add('active');
            }
        });
    }, { threshold: 0.3 });

    sections.forEach(s => observer.observe(s.section));
}

// ── Tab Indicator ───────────────────────────────────────────────
function initTabIndicator() {
    const activeTab = document.querySelector('.tab.active');
    if (activeTab) {
        updateTabIndicator(activeTab);
    }
    window.addEventListener('resize', () => {
        const currentActive = document.querySelector('.tab.active');
        if (currentActive) updateTabIndicator(currentActive);
    });
}

function updateTabIndicator(btn) {
    const indicator = document.getElementById('tab-indicator');
    if (!indicator || !btn) return;
    const bar = btn.parentElement;
    const barRect = bar.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();

    indicator.style.left = `${btnRect.left - barRect.left + bar.scrollLeft}px`;
    indicator.style.width = `${btnRect.width}px`;
}

// ── Character Count ─────────────────────────────────────────────
function initCharCount() {
    const textarea = document.getElementById('nl-input');
    const counter = document.getElementById('char-count');
    if (!textarea || !counter) return;

    function update() {
        counter.textContent = textarea.value.length;
    }

    textarea.addEventListener('input', update);
    update();
}

// ── Input Validation & Steppers ─────────────────────────────────
function initInputValidation() {
    const candidatesInput = document.getElementById('candidates');
    const iterationsInput = document.getElementById('iterations');

    if (candidatesInput) {
        candidatesInput.addEventListener('change', () => {
            let val = parseInt(candidatesInput.value) || 5;
            val = Math.max(1, Math.min(12, val));
            candidatesInput.value = val;
        });
    }

    if (iterationsInput) {
        iterationsInput.addEventListener('change', () => {
            let val = parseInt(iterationsInput.value) || 300;
            val = Math.max(50, Math.min(2000, val));
            iterationsInput.value = val;
        });
    }
}

// ── Helpers ──────────────────────────────────────────────────────
function adjustValue(id, delta) {
    const input = document.getElementById(id);
    let val = parseInt(input.value) + delta;
    val = Math.max(parseInt(input.min), Math.min(parseInt(input.max), val));
    input.value = val;
}

function loadExample(index) {
    const textarea = document.getElementById('nl-input');
    textarea.value = EXAMPLES[index];
    textarea.focus();
    textarea.dispatchEvent(new Event('input'));

    // Highlight chip
    document.querySelectorAll('.example-chip').forEach((chip, i) => {
        chip.classList.toggle('active', i === index);
    });

    // Smooth pulse on textarea
    textarea.style.boxShadow = '0 0 0 3px rgba(107,138,255,0.3), 0 0 30px rgba(107,138,255,0.15)';
    setTimeout(() => {
        textarea.style.boxShadow = '';
    }, 800);
}

function switchTab(btn) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const target = document.getElementById(btn.dataset.tab);
    if (target) target.classList.add('active');
    updateTabIndicator(btn);
}

function formatDimName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Smooth Number Counter ───────────────────────────────────────
function animateNumber(element, start, end, duration = 1200, decimals = 4) {
    if (!element) return;
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Quartic ease out
        const ease = 1 - Math.pow(1 - progress, 4);
        const current = start + (end - start) * ease;
        element.textContent = current.toFixed(decimals);
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

// ── Downloads & Exports ──────────────────────────────────────────
function downloadImage(imgId, filename = 'planagent_plan.png') {
    const img = document.getElementById(imgId);
    if (!img || !img.src) {
        showError('No image available to download.');
        return;
    }
    const a = document.createElement('a');
    a.href = img.src;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function downloadCurrentLightbox() {
    const img = document.getElementById('lightbox-img');
    if (!img || !img.src) return;
    const a = document.createElement('a');
    a.href = img.src;
    a.download = 'planagent_view.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function exportDesignJson() {
    if (!pipelineResult) {
        showError('Please generate a design first before exporting.');
        return;
    }

    const exportData = {
        title: 'PlanAgent Design Results',
        timestamp: new Date().toISOString(),
        prompt: document.getElementById('nl-input').value.trim(),
        elapsed_seconds: pipelineResult.elapsed,
        summary: {
            before_score: pipelineResult.before_score,
            after_score: pipelineResult.after_score,
            improvement: pipelineResult.improvement,
            before_violations: pipelineResult.before_violations,
            after_violations: pipelineResult.after_violations,
            utilization_before_pct: pipelineResult.utilization_before,
            utilization_after_pct: pipelineResult.utilization_after,
        },
        requirements: pipelineResult.requirements,
        spatial_graph: pipelineResult.graph_summary,
        scores_breakdown: {
            before: pipelineResult.before_dimension_scores,
            after: pipelineResult.after_dimension_scores,
        },
        violations: {
            before: pipelineResult.before_violation_details,
            after: pipelineResult.after_violation_details,
        },
        optimized_rooms: pipelineResult.optimized_rooms,
        history: pipelineResult.history || [],
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `planagent_design_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ── Lightbox ────────────────────────────────────────────────────
function openLightbox(imgEl) {
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    lightboxImg.src = imgEl.src;
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
}

// Close lightbox on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});

// ── Error Toast ─────────────────────────────────────────────────
function showError(message) {
    const toast = document.getElementById('error-toast');
    const text = document.getElementById('error-toast-text');
    text.textContent = message;
    toast.style.display = 'flex';

    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => hideError(), 6000);
}

function hideError() {
    const toast = document.getElementById('error-toast');
    toast.style.display = 'none';
}

// ── Pipeline Steps Animation ─────────────────────────────────────
const STEP_MESSAGES = [
    { text: 'Parsing natural language requirements', icon: '💬' },
    { text: 'Building spatial relationship graph', icon: '🔗' },
    { text: 'Generating candidate floor plans', icon: '📐' },
    { text: 'Evaluating with spatial critic', icon: '✅' },
    { text: 'Running simulated annealing optimization', icon: '⚡' },
    { text: 'Rendering publication visualizations', icon: '🎨' },
];

let loadingInterval = null;

function showLoading() {
    const overlay = document.getElementById('loading-overlay');
    const bar = document.getElementById('progress-bar');
    const stepText = document.getElementById('loading-step');
    const stepsList = document.getElementById('loading-steps-list');
    overlay.style.display = 'flex';
    bar.style.width = '0%';

    // Build steps list
    stepsList.innerHTML = STEP_MESSAGES.map((s, i) => `
        <div class="loading-step-item" id="loading-step-${i}">
            <span class="step-check">${s.icon}</span>
            <span>${s.text}</span>
        </div>
    `).join('');

    let step = 0;
    clearInterval(loadingInterval);
    loadingInterval = setInterval(() => {
        if (step < STEP_MESSAGES.length) {
            stepText.textContent = STEP_MESSAGES[step].text + '...';
            bar.style.width = `${((step + 1) / STEP_MESSAGES.length) * 92}%`;

            for (let i = 0; i < STEP_MESSAGES.length; i++) {
                const el = document.getElementById(`loading-step-${i}`);
                if (!el) continue;
                el.classList.remove('active', 'done');
                if (i < step) el.classList.add('done');
                else if (i === step) el.classList.add('active');
            }

            document.querySelectorAll('.flow-step').forEach((el, i) => {
                el.classList.remove('active', 'completed');
                if (i < step) el.classList.add('completed');
                else if (i === step) el.classList.add('active');
            });

            step++;
        }
    }, 700);
}

function hideLoading() {
    clearInterval(loadingInterval);
    const overlay = document.getElementById('loading-overlay');
    const bar = document.getElementById('progress-bar');
    bar.style.width = '100%';

    STEP_MESSAGES.forEach((_, i) => {
        const el = document.getElementById(`loading-step-${i}`);
        if (el) {
            el.classList.remove('active');
            el.classList.add('done');
        }
    });

    document.querySelectorAll('.flow-step').forEach(el => {
        el.classList.remove('active');
        el.classList.add('completed');
    });

    setTimeout(() => {
        overlay.style.display = 'none';
    }, 500);
}

// ── Run Pipeline ─────────────────────────────────────────────────
async function runPipeline() {
    const btn = document.getElementById('run-btn');
    const input = document.getElementById('nl-input').value.trim();
    const candidates = parseInt(document.getElementById('candidates').value) || 5;
    const iterations = parseInt(document.getElementById('iterations').value) || 300;
    const backend = document.getElementById('backend').value;

    if (!input) {
        showError('Please enter an architectural brief before generating.');
        return;
    }

    btn.disabled = true;
    btn.querySelector('.btn-content').style.display = 'none';
    btn.querySelector('.btn-loading').style.display = 'flex';

    showLoading();

    try {
        const response = await fetch('/api/pipeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input, candidates, iterations, backend }),
        });

        const data = await response.json();

        if (data.error) {
            showError('Pipeline error: ' + data.error);
            return;
        }

        pipelineResult = data;
        renderResults(data);

    } catch (err) {
        console.error(err);
        showError('Connection error: ' + err.message);
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.querySelector('.btn-content').style.display = 'flex';
        btn.querySelector('.btn-loading').style.display = 'none';
    }
}

// ── Render Results ───────────────────────────────────────────────
function renderResults(data) {
    const section = document.getElementById('results-section');
    section.style.display = 'block';

    setTimeout(() => {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        const activeTab = document.querySelector('.tab.active');
        if (activeTab) updateTabIndicator(activeTab);
    }, 180);

    // Meta
    document.getElementById('elapsed-time').textContent = `${data.elapsed}s`;
    const impText = data.improvement >= 0 ? `+${data.improvement}` : `${data.improvement}`;
    document.getElementById('improvement-text').textContent = `${impText}`;

    // Score gauges & count-up
    animateGauge('gauge-before', data.before_score);
    animateGauge('gauge-after', data.after_score);
    animateNumber(document.getElementById('score-before'), 0, data.before_score, 1400, 4);
    animateNumber(document.getElementById('score-after'), 0, data.after_score, 1400, 4);
    document.getElementById('score-delta').textContent = impText;

    // Violations
    document.getElementById('violations-before').textContent = `${data.before_violations} violation${data.before_violations !== 1 ? 's' : ''}`;
    document.getElementById('violations-after').textContent = `${data.after_violations} violation${data.after_violations !== 1 ? 's' : ''}`;

    const resolvedCount = data.before_violations - data.after_violations;
    document.getElementById('violations-delta').textContent =
        resolvedCount > 0
        ? `${resolvedCount} violation${resolvedCount !== 1 ? 's' : ''} resolved`
        : resolvedCount === 0 ? 'No change' : `${Math.abs(resolvedCount)} added`;

    // Utilization
    document.getElementById('util-before').textContent = `${data.utilization_before}%`;
    document.getElementById('util-after').textContent = `${data.utilization_after}%`;

    // Delta bar
    const deltaBar = document.getElementById('delta-bar');
    if (deltaBar) {
        const improvement = Math.min(Math.max(data.improvement, 0), 1);
        setTimeout(() => {
            deltaBar.style.width = `${improvement * 100}%`;
        }, 200);
    }

    // Optimization tab (primary)
    document.getElementById('before-img').src = 'data:image/png;base64,' + data.before_plan_img;
    document.getElementById('after-img').src = 'data:image/png;base64,' + data.after_plan_img;
    if (data.history_img) {
        document.getElementById('history-img').src = 'data:image/png;base64,' + data.history_img;
    }

    // Candidates
    renderCandidates(data.candidates, data.best_candidate_index);

    // Spatial graph
    document.getElementById('graph-img').src = 'data:image/png;base64,' + data.spatial_graph_img;

    // Requirements tab
    renderRooms(data.requirements.rooms);
    renderRelationships(data.requirements.relationships);
    document.getElementById('plot-info').innerHTML =
        `📏 Plot: <strong>${data.requirements.plot_width} × ${data.requirements.plot_height} ft</strong> (${data.requirements.plot_width * data.requirements.plot_height} sqft)`;

    // Scoring
    renderDimensionBars(data.before_dimension_scores, data.after_dimension_scores);
    renderViolations(data.before_violation_details, data.after_violation_details);
    renderRoomsTable(data.optimized_rooms);
}

// ── Animate Score Gauge ─────────────────────────────────────────
function animateGauge(id, score) {
    const el = document.getElementById(id);
    if (!el) return;

    const circumference = 2 * Math.PI * 52; // r=52
    const offset = circumference * (1 - Math.min(Math.max(score, 0), 1));

    el.style.transition = 'none';
    el.style.strokeDashoffset = circumference;

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            el.style.transition = 'stroke-dashoffset 1.5s cubic-bezier(0.16, 1, 0.3, 1)';
            el.style.strokeDashoffset = offset;
        });
    });
}

// ── Render Rooms ─────────────────────────────────────────────────
function renderRooms(rooms) {
    const container = document.getElementById('rooms-list');
    const countEl = document.getElementById('rooms-count');
    if (countEl) countEl.textContent = rooms.length;

    container.innerHTML = rooms.map((r, i) => `
        <div class="room-item" style="animation: fadeUp 0.3s ease ${i * 0.05}s both">
            <div class="room-dot" style="background: ${ROOM_COLORS[r.room_type] || '#888'}; color: ${ROOM_COLORS[r.room_type] || '#888'}"></div>
            <span class="room-name">${ROOM_ICONS[r.room_type] || '📦'} ${r.name}</span>
            <span class="room-meta">${r.min_width}×${r.min_height} ft · ${r.preferred_area} sqft</span>
        </div>
    `).join('');
}

// ── Render Relationships ─────────────────────────────────────────
function renderRelationships(rels) {
    const container = document.getElementById('relationships-list');
    const countEl = document.getElementById('rels-count');
    if (countEl) countEl.textContent = rels.length;

    if (rels.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.82rem; padding: 0.5rem 0.85rem;">No explicit relationships defined. Default layout conventions applied.</div>`;
        return;
    }

    container.innerHTML = rels.map((r, i) => `
        <div class="rel-item" style="animation: fadeUp 0.3s ease ${i * 0.05}s both">
            <span class="rel-room">${r.room_a}</span>
            <span class="rel-type ${r.relationship}">${r.relationship.replace(/_/g, ' ')}</span>
            <span class="rel-room">${r.room_b}</span>
        </div>
    `).join('');
}

// ── Render Candidates ────────────────────────────────────────────
function renderCandidates(candidates, bestIdx) {
    const container = document.getElementById('candidates-grid');
    container.innerHTML = candidates.map((c, i) => `
        <div class="candidate-card glass-card ${c.index === bestIdx ? 'best-candidate' : ''}" style="animation: fadeUp 0.4s ease ${i * 0.08}s both">
            <div class="candidate-header">
                <span class="candidate-number">Candidate ${c.index}</span>
                <div class="candidate-score">
                    <span class="candidate-score-value">${c.score}</span>
                    ${c.index === bestIdx
                        ? '<span class="candidate-badge badge-best">★ Best Candidate</span>'
                        : c.violations > 0
                            ? `<span class="candidate-badge badge-violations">${c.violations} violation${c.violations !== 1 ? 's' : ''}</span>`
                            : ''}
                </div>
            </div>
            <div class="candidate-img-wrapper">
                <img src="data:image/png;base64,${c.image}" alt="Candidate ${c.index}" onclick="openLightbox(this)" title="Click to view full size">
            </div>
        </div>
    `).join('');
}

// ── Render Dimension Bars (Dual Track Before vs After) ───────────
function renderDimensionBars(before, after) {
    const container = document.getElementById('dimension-bars');
    const dims = Object.keys(after);

    container.innerHTML = dims.map((dim, i) => {
        const bVal = before[dim] !== undefined ? before[dim] : 0;
        const aVal = after[dim] !== undefined ? after[dim] : 0;
        const diff = aVal - bVal;
        const improved = diff > 0.001;
        const decreased = diff < -0.001;

        let badgeClass = 'same';
        let badgeText = '= Same';
        if (improved) {
            badgeClass = 'improved';
            badgeText = `+${diff.toFixed(3)}`;
        } else if (decreased) {
            badgeClass = 'decreased';
            badgeText = `${diff.toFixed(3)}`;
        }

        return `
            <div class="dim-row" style="animation: fadeUp 0.3s ease ${i * 0.05}s both">
                <div class="dim-label-row">
                    <span class="dim-name">${formatDimName(dim)}</span>
                    <span class="dim-delta-badge ${badgeClass}">${badgeText}</span>
                </div>
                <div class="dim-bars-wrapper">
                    <div class="dim-bar-row">
                        <span class="dim-bar-tag before">Before</span>
                        <div class="dim-bar-track">
                            <div class="dim-bar-fill before-bar" style="width: ${Math.round(bVal * 100)}%"></div>
                        </div>
                        <span class="dim-val before-val">${bVal.toFixed(3)}</span>
                    </div>
                    <div class="dim-bar-row">
                        <span class="dim-bar-tag after">After</span>
                        <div class="dim-bar-track">
                            <div class="dim-bar-fill after-bar" style="width: ${Math.round(aVal * 100)}%"></div>
                        </div>
                        <span class="dim-val after-val">${aVal.toFixed(3)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ── Render Violations ────────────────────────────────────────────
function renderViolations(before, after) {
    const container = document.getElementById('violations-list');

    if (before.length === 0 && after.length === 0) {
        container.innerHTML = `
            <div class="no-violations">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22">
                    <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>
                </svg>
                All spatial constraints perfectly satisfied!
            </div>`;
        return;
    }

    let html = '';

    // Show resolved violations (were in before, not in after)
    const afterDescs = new Set(after.map(v => v.description));
    for (const v of before) {
        if (!afterDescs.has(v.description)) {
            html += `<div class="violation-item resolved">
                <span class="violation-category">[${v.category}]</span>
                ${v.description} — ✓ RESOLVED
            </div>`;
        }
    }

    // Show remaining violations
    for (const v of after) {
        html += `<div class="violation-item after-v">
            <span class="violation-category">[${v.category}]</span>
            ${v.description}
        </div>`;
    }

    if (!html) {
        html = `<div class="no-violations">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22">
                <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>
            </svg>
            All constraints resolved after optimization!
        </div>`;
    }

    container.innerHTML = html;
}

// ── Render Rooms Table ───────────────────────────────────────────
function renderRoomsTable(rooms) {
    const tbody = document.getElementById('rooms-table-body');
    tbody.innerHTML = rooms.map((r, i) => `
        <tr style="animation: fadeUp 0.3s ease ${i * 0.04}s both">
            <td>
                <span style="color: ${ROOM_COLORS[r.room_type] || '#888'}; margin-right: 0.3rem">●</span>
                ${r.name}
            </td>
            <td>${formatDimName(r.room_type)}</td>
            <td class="mono">(${r.x.toFixed(1)}, ${r.y.toFixed(1)})</td>
            <td class="mono">${r.width.toFixed(1)} × ${r.height.toFixed(1)}</td>
            <td class="mono">${(r.width * r.height).toFixed(0)}</td>
        </tr>
    `).join('');
}

// ── Keyboard Shortcuts ──────────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        runPipeline();
    }
});
