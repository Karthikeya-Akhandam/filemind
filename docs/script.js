// Brain Network Generator
const nodes = [
  // Top of the brain
  { x: 250, y: 60, delay: 0.0 },
  { x: 210, y: 70, delay: 0.1 },
  { x: 290, y: 70, delay: 0.15 },
  { x: 180, y: 90, delay: 0.2 },
  { x: 320, y: 90, delay: 0.25 },

  // Upper lobes
  { x: 150, y: 120, delay: 0.3 },
  { x: 200, y: 110, delay: 0.35 },
  { x: 250, y: 110, delay: 0.4 },
  { x: 300, y: 110, delay: 0.45 },
  { x: 350, y: 120, delay: 0.5 },

  // Mid-section lobes
  { x: 130, y: 160, delay: 0.55 },
  { x: 180, y: 140, delay: 0.6 },
  { x: 230, y: 145, delay: 0.65 },
  { x: 270, y: 145, delay: 0.7 },
  { x: 320, y: 140, delay: 0.75 },
  { x: 370, y: 160, delay: 0.8 },

  // Center/Lower-Mid
  { x: 140, y: 200, delay: 0.85 },
  { x: 190, y: 180, delay: 0.9 },
  { x: 250, y: 180, delay: 0.95 },
  { x: 310, y: 180, delay: 1.0 },
  { x: 360, y: 200, delay: 1.05 },

  // Lower lobes
  { x: 160, y: 230, delay: 1.1 },
  { x: 220, y: 220, delay: 1.15 },
  { x: 280, y: 220, delay: 1.2 },
  { x: 340, y: 230, delay: 1.25 },

  // Bottom part / brainstem area
  { x: 200, y: 260, delay: 1.3 },
  { x: 250, y: 270, delay: 1.35 },
  { x: 300, y: 260, delay: 1.4 },
  { x: 250, y: 290, delay: 1.45 }
];

// Create connections between nearby nodes
function createConnections() {
  const connections = [];

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      // Connect nodes within a certain distance
      if (distance < 60) {
        connections.push({
          from: nodes[i],
          to: nodes[j],
          delay: (i + j) * 0.05,
        });
      }
    }
  }

  return connections;
}

// Render brain network
function renderBrainNetwork() {
  const connectionsGroup = document.getElementById('connections');
  const nodesGroup = document.getElementById('nodes');
  const connections = createConnections();

  // Render connections
  connections.forEach((conn, idx) => {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', conn.from.x);
    line.setAttribute('y1', conn.from.y);
    line.setAttribute('x2', conn.to.x);
    line.setAttribute('y2', conn.to.y);
    line.setAttribute('stroke', '#E66B44');
    line.setAttribute('stroke-width', '1');
    line.setAttribute('stroke-opacity', '0.3');
    line.setAttribute('stroke-linecap', 'round');
    line.classList.add('connection');
    line.style.animationDelay = `${conn.delay * 0.5}s`;
    connectionsGroup.appendChild(line);
  });

  // Render nodes
  nodes.forEach((node, idx) => {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', node.x);
    circle.setAttribute('cy', node.y);
    circle.setAttribute('r', '3');
    circle.setAttribute('fill', '#E66B44');
    circle.classList.add('node');
    circle.style.animationDelay = `${node.delay}s`;
    nodesGroup.appendChild(circle);
  });
}

// Generic copy-to-clipboard for all copy buttons
function initCopyButtons() {
  document.querySelectorAll('.copy-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const text = btn.getAttribute('data-copy');
      if (!text) return;

      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = text;
          textArea.style.position = 'fixed';
          textArea.style.left = '-999999px';
          textArea.style.top = '-999999px';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();
          document.execCommand('copy');
          textArea.remove();
        }

        const copyIcon = btn.querySelector('.copy-icon');
        const checkIcon = btn.querySelector('.check-icon');
        copyIcon.classList.add('hidden');
        checkIcon.classList.remove('hidden');

        setTimeout(() => {
          copyIcon.classList.remove('hidden');
          checkIcon.classList.add('hidden');
        }, 2000);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    });
  });
}

// Tab switching
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');

      tabBtns.forEach((b) => b.classList.remove('active'));
      tabPanels.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      document.querySelector(`.tab-panel[data-tab="${tab}"]`).classList.add('active');
    });
  });
}

// Fetch and display current version from version.txt
function fetchVersion() {
  fetch('version.txt')
    .then((res) => {
      if (!res.ok) throw new Error('version.txt not found');
      return res.text();
    })
    .then((text) => {
      let version = text.trim();
      if (!version.startsWith('v')) version = 'v' + version;
      document.getElementById('currentVersion').textContent = version;
    })
    .catch(() => {
      document.getElementById('currentVersion').textContent = 'latest';
    });
}

// Find a matching asset for a platform
function findAsset(assets, platform) {
  if (!assets || assets.length === 0) return null;
  return assets.find((a) => {
    const name = a.name.toLowerCase();
    if (platform === 'windows') return name.endsWith('.exe');
    if (platform === 'linux') return name.includes('linux');
    if (platform === 'macos') return name.includes('macos');
    return false;
  }) || null;
}

// Create badge HTML for a release
function createBadgeHTML(release, isLatestStable) {
  if (isLatestStable) {
    return '<span class="release-badge latest">Latest</span>';
  }
  if (release.prerelease) {
    return '<span class="release-badge prerelease">Pre-release</span>';
  }
  return '';
}

// Download icon SVG
const downloadIconSVG = '<svg class="release-download-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>';

// Populate Windows dropdown
function populateWindowsDropdown(releases) {
  const list = document.getElementById('windowsReleaseList');
  if (!list) return;

  // Find the first non-prerelease for "Latest" badge
  const latestStableTag = releases.find((r) => !r.prerelease)?.tag_name || null;

  const rows = [];
  for (const release of releases) {
    const asset = findAsset(release.assets, 'windows');
    if (!asset) continue;

    const isLatestStable = release.tag_name === latestStableTag;
    const badge = createBadgeHTML(release, isLatestStable);
    const li = document.createElement('li');
    li.innerHTML = `<a href="${asset.browser_download_url}" class="release-row-link" role="option"><span class="release-version">${release.tag_name}</span>${badge}${downloadIconSVG}</a>`;
    rows.push(li);
  }

  if (rows.length === 0) {
    showEmptyState('windowsReleaseList', 'No Windows releases available');
    return;
  }

  list.innerHTML = '';
  rows.forEach((li) => list.appendChild(li));
}

// Populate Linux/macOS dropdown
function populateLinuxMacDropdown(releases) {
  const list = document.getElementById('linuxMacReleaseList');
  if (!list) return;

  const latestStableTag = releases.find((r) => !r.prerelease)?.tag_name || null;

  const rows = [];
  for (const release of releases) {
    const linuxAsset = findAsset(release.assets, 'linux');
    const macAsset = findAsset(release.assets, 'macos');

    // Skip release if neither platform has an asset
    if (!linuxAsset && !macAsset) continue;

    const isLatestStable = release.tag_name === latestStableTag;
    const badge = createBadgeHTML(release, isLatestStable);

    const linuxLink = linuxAsset
      ? `<a href="${linuxAsset.browser_download_url}" class="release-platform-link">Linux</a>`
      : '<span class="release-platform-link disabled">Linux</span>';

    const macLink = macAsset
      ? `<a href="${macAsset.browser_download_url}" class="release-platform-link">macOS</a>`
      : '<span class="release-platform-link disabled">macOS</span>';

    const li = document.createElement('li');
    li.innerHTML = `<div class="release-row-multi"><div class="release-row-info"><span class="release-version">${release.tag_name}</span>${badge}</div><div class="release-platform-links">${linuxLink}${macLink}</div></div>`;
    rows.push(li);
  }

  if (rows.length === 0) {
    showEmptyState('linuxMacReleaseList', 'No binary releases available');
    return;
  }

  list.innerHTML = '';
  rows.forEach((li) => list.appendChild(li));
}

// Show empty state in a dropdown list
function showEmptyState(listId, message) {
  const list = document.getElementById(listId);
  if (!list) return;
  list.innerHTML = `<li class="release-dropdown-empty">${message}</li>`;
}

// Close all open dropdowns
function closeAllDropdowns() {
  document.querySelectorAll('.release-dropdown.open').forEach((dd) => {
    dd.classList.remove('open');
  });
  document.querySelectorAll('.dropdown-toggle').forEach((btn) => {
    btn.setAttribute('aria-expanded', 'false');
  });
}

// Initialize dropdown toggle behavior
function initDropdowns() {
  document.querySelectorAll('.dropdown-toggle').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const wrapper = btn.closest('.dropdown-wrapper');
      const dropdown = wrapper.querySelector('.release-dropdown');
      const isOpen = dropdown.classList.contains('open');

      // Close all dropdowns first
      closeAllDropdowns();

      // Toggle the clicked one (if it was closed)
      if (!isOpen) {
        dropdown.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
  });

  // Click outside closes dropdowns
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-wrapper')) {
      closeAllDropdowns();
    }
  });

  // Escape key closes dropdowns and returns focus
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const openDropdown = document.querySelector('.release-dropdown.open');
      if (openDropdown) {
        const wrapper = openDropdown.closest('.dropdown-wrapper');
        const toggle = wrapper.querySelector('.dropdown-toggle');
        closeAllDropdowns();
        toggle.focus();
      }
    }
  });
}

// Fetch releases.json and populate dropdowns
function fetchReleases() {
  fetch('releases.json')
    .then((res) => {
      if (!res.ok) throw new Error('releases.json not found');
      return res.json();
    })
    .then((releases) => {
      if (!Array.isArray(releases) || releases.length === 0) {
        showEmptyState('windowsReleaseList', 'No releases available');
        showEmptyState('linuxMacReleaseList', 'No releases available');
        return;
      }

      populateWindowsDropdown(releases);
      populateLinuxMacDropdown(releases);
    })
    .catch(() => {
      showEmptyState('windowsReleaseList', 'Could not load releases');
      showEmptyState('linuxMacReleaseList', 'Could not load releases');
    });
}

// Auto-select tab based on user's OS
function detectOS() {
  const ua = navigator.userAgent.toLowerCase();
  let tab = 'linux-mac'; // default

  if (ua.includes('win')) {
    tab = 'windows';
  } else if (ua.includes('mac')) {
    tab = 'linux-mac';
  } else if (ua.includes('linux')) {
    tab = 'linux-mac';
  }

  const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
  if (btn) btn.click();
}

// Scroll animations
function initScrollAnimations() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }
      });
    },
    {
      threshold: 0.1,
    }
  );

  // Observe feature cards
  document.querySelectorAll('.feature-card').forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = `opacity 0.5s ease ${index * 0.1}s, transform 0.5s ease ${index * 0.1}s`;
    observer.observe(card);
  });

  // Observe download section
  const downloadHeader = document.querySelector('.download-header');
  if (downloadHeader) {
    downloadHeader.style.opacity = '0';
    downloadHeader.style.transform = 'translateY(20px)';
    downloadHeader.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(downloadHeader);
  }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  renderBrainNetwork();
  initCopyButtons();
  initTabs();
  initScrollAnimations();
  initDropdowns();
  fetchVersion();
  fetchReleases();
  detectOS();
});
