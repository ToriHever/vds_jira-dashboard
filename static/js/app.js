let allIssues = [];
let sortColumn = null;
let sortDirection = 'asc';
let network = null;
let graphData = { nodes: [], edges: [] };

// URL вашего Jira сервера
const JIRA_BASE_URL = 'https://jira.ddos-guard.net';

// Функция для генерации ссылки на задачу
function getJiraIssueLink(issueKey) {
    return `${JIRA_BASE_URL}/browse/${issueKey}`;
}

// Функция для определения CSS класса строки по типу задачи
function getRowClass(issueType) {
    if (!issueType) return '';
    
    const type = issueType.toLowerCase();
    
    if (type.includes('story') || type.includes('история')) {
        return 'row-story';
    }
    
    if (type.includes('epic') || type === 'эпик') {
        return 'row-epic';
    }
    
    return '';
}

function getSortIcon(column) {
    if (sortColumn === column) {
        return sortDirection === 'asc' ? '▲' : '▼';
    }
    return '⇅';
}
    
function sortTable(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'asc';
    }
    applyTableFilters();
}

let activeFilters = {
    type: '',
    status: '',
    priority: '',
    sprint: ''
};

function applyTableFilters() {
    activeFilters.type = document.getElementById('filterType')?.value || '';
    activeFilters.status = document.getElementById('filterStatus')?.value || '';
    activeFilters.priority = document.getElementById('filterPriority')?.value || '';
    activeFilters.sprint = document.getElementById('filterSprint')?.value || '';
    
    let filtered = allIssues.filter(issue => {
        if (activeFilters.type && issue.issue_type !== activeFilters.type) return false;
        if (activeFilters.status && issue.status !== activeFilters.status) return false;
        if (activeFilters.priority && issue.priority !== activeFilters.priority) return false;
        if (activeFilters.sprint && issue.sprint !== activeFilters.sprint) return false;
        return true;
    });
    
    if (sortColumn) {
        filtered = [...filtered].sort((a, b) => {
            let aVal = a[sortColumn];
            let bVal = b[sortColumn];
            
            if (aVal === null || aVal === undefined || aVal === '') aVal = '';
            if (bVal === null || bVal === undefined || bVal === '') bVal = '';
            
            if (sortColumn === 'time_original_estimate' || sortColumn === 'time_spent') {
                aVal = parseFloat(aVal) || 0;
                bVal = parseFloat(bVal) || 0;
            }
            
            if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }
    
    renderIssuesTable(filtered);
    
    if (document.getElementById('filterType')) {
        document.getElementById('filterType').value = activeFilters.type;
        document.getElementById('filterStatus').value = activeFilters.status;
        document.getElementById('filterPriority').value = activeFilters.priority;
        document.getElementById('filterSprint').value = activeFilters.sprint;
    }
}

function clearTableFilters() {
    activeFilters = { type: '', status: '', priority: '', sprint: '' };
    sortColumn = null;
    sortDirection = 'asc';
    renderIssuesTable(allIssues);
}
    
async function loadData() {
    try {
        const statsResponse = await fetch('/api/statistics');
        const stats = await statsResponse.json();
    
        document.getElementById('totalIssues').textContent = stats.total;
        document.getElementById('totalLinks').textContent = stats.total_links;
    
        const inProgressCount = stats.by_status.find(s => s.status === 'В работе')?.count || 0;
        const completedCount = stats.by_status.find(s => s.status === 'Готово')?.count || 0;
    
        document.getElementById('inProgress').textContent = inProgressCount;
        document.getElementById('completed').textContent = completedCount;
    
        const issuesResponse = await fetch('/api/issues');
        allIssues = await issuesResponse.json();
    
        renderIssuesTable(allIssues);
        renderSprintsTable(stats.by_sprint);
        renderStatusTable(stats.by_status);
    
        if (allIssues.length > 0) {
            document.getElementById('lastSync').textContent = 
                `Последняя синхронизация: ${allIssues[0].last_synced}`;
        }

        await loadSprintStats();
    
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        alert('Ошибка загрузки данных. Проверьте подключение к серверу.');
    }
}

async function loadSprintStats() {
    try {
        const response = await fetch('/api/current-sprint-stats');
        const stats = await response.json();

        if (stats.error) {
            document.getElementById('sprintLoadPercent').textContent = 'N/A';
            document.getElementById('sprintName').textContent = 'Нет данных';
            return;
        }

        document.getElementById('sprintLoadPercent').textContent = `${stats.workload_percent}%`;
        document.getElementById('sprintName').textContent = stats.sprint_name;

        const icon = document.getElementById('sprintLoadIcon');
        const card = document.getElementById('sprintLoadCard');

        if (stats.workload_status === 'overloaded') {
            icon.textContent = '🔴';
            card.style.borderLeft = '5px solid #e74c3c';
        } else if (stats.workload_status === 'full') {
            icon.textContent = '🟡';
            card.style.borderLeft = '5px solid #f39c12';
        } else if (stats.workload_status === 'normal') {
            icon.textContent = '🟢';
            card.style.borderLeft = '5px solid #27ae60';
        } else {
            icon.textContent = '⚪';
            card.style.borderLeft = '5px solid #95a5a6';
        }

        renderSprintLoadDetails(stats);

    } catch (error) {
        console.error('Ошибка загрузки статистики спринта:', error);
    }
}

function renderSprintLoadDetails(stats) {
    const statusText = {
        'light': 'Лёгкая загрузка',
        'normal': 'Нормальная загрузка',
        'full': 'Полная загрузка',
        'overloaded': 'Перегружен'
    };
    
    const statusClass = {
        'light': 'status-light',
        'normal': 'status-normal',
        'full': 'status-full',
        'overloaded': 'status-overloaded'
    };
    
    const html = `
<div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
    <h3>${stats.sprint_name}</h3>
    <span class="status-indicator ${statusClass[stats.workload_status]}">
        ${statusText[stats.workload_status]}
    </span>
</div>

<div class="sprint-load-container">
    <div class="sprint-metric">
        <h3>📊 Capacity спринта</h3>
        <div class="value">${stats.sprint_capacity}ч</div>
        <div class="subtext">2 недели работы</div>
    </div>
    
    <div class="sprint-metric">
        <h3>📝 Оценка задач</h3>
        <div class="value">${stats.total_estimated}ч</div>
        <div class="subtext">${stats.workload_percent}% от capacity</div>
        <div class="progress-bar">
            <div class="progress-fill ${stats.workload_percent > 100 ? 'danger' : stats.workload_percent > 90 ? 'warning' : ''}" 
                 style="width: ${Math.min(stats.workload_percent, 100)}%">
                ${stats.workload_percent}%
            </div>
        </div>
    </div>
    
    <div class="sprint-metric">
        <h3>⏱️ Затрачено времени</h3>
        <div class="value">${stats.total_spent}ч</div>
        <div class="subtext">${stats.time_used_percent}% от capacity</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${Math.min(stats.time_used_percent, 100)}%">
                ${stats.time_used_percent}%
            </div>
        </div>
    </div>
    
    <div class="sprint-metric">
        <h3>✅ Прогресс задач</h3>
        <div class="value">${stats.completed_tasks}/${stats.total_tasks}</div>
        <div class="subtext">${stats.progress_percent}% завершено</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${stats.progress_percent}%">
                ${stats.progress_percent}%
            </div>
        </div>
    </div>
    
    <div class="sprint-metric">
        <h3>🔄 Активные задачи</h3>
        <div class="value">${stats.in_progress_tasks}</div>
        <div class="subtext">В работе сейчас</div>
    </div>
    
    <div class="sprint-metric">
        <h3>📋 Открытые задачи</h3>
        <div class="value">${stats.open_tasks}</div>
        <div class="subtext">Ожидают начала</div>
    </div>
    
    <div class="sprint-metric" style="grid-column: span 2;">
        <h3>⚡ Оставшаяся capacity</h3>
        <div class="value">${stats.remaining_capacity}ч</div>
        <div class="subtext">
            Осталось работы: ${stats.remaining_work}ч
            ${stats.remaining_work > stats.remaining_capacity ? 
                '<br><span style="color: #e74c3c; font-weight: bold;">⚠️ Работы больше чем capacity!</span>' : 
                '<br><span style="color: #27ae60;">✓ В пределах capacity</span>'}
        </div>
    </div>
</div>

<div style="background: #f9f9f9; padding: 20px; border-radius: 10px; margin-top: 20px;">
    <h3>💡 Рекомендации</h3>
    ${getRecommendations(stats)}
</div>

<div style="margin-top: 30px;">
    <div id="sprintIssuesTable"></div>
</div>
    `;
    
    document.getElementById('sprintLoadDetails').innerHTML = html;
    document.getElementById('sprintLoadTitle').textContent = `⚡ Загруженность: ${stats.sprint_name}`;
    loadCurrentSprintIssues();
}

function getRecommendations(stats) {
    const recommendations = [];
    
    if (stats.workload_percent > 100) {
        recommendations.push('🔴 <strong>Спринт перегружен!</strong> Оценка задач превышает capacity на ' + (stats.workload_percent - 100).toFixed(1) + '%. Рекомендуется перенести часть задач.');
    } else if (stats.workload_percent > 90) {
        recommendations.push('🟡 <strong>Высокая загрузка.</strong> Спринт загружен почти полностью. Будьте осторожны с добавлением новых задач.');
    } else if (stats.workload_percent < 70) {
        recommendations.push('⚪ <strong>Низкая загрузка.</strong> В спринте есть место для дополнительных задач (~' + (80 - stats.total_estimated).toFixed(1) + 'ч).');
    } else {
        recommendations.push('🟢 <strong>Оптимальная загрузка.</strong> Спринт загружен хорошо.');
    }
    
    if (stats.remaining_work > stats.remaining_capacity && stats.progress_percent < 80) {
        recommendations.push('⚠️ <strong>Риск не завершить спринт.</strong> Оставшейся работы больше чем свободного времени.');
    }
    
    if (stats.open_tasks > stats.in_progress_tasks * 2) {
        recommendations.push('📋 <strong>Много задач в очереди.</strong> Рекомендуется начать работу над открытыми задачами.');
    }
    
    if (stats.progress_percent > 70 && stats.time_used_percent < 70) {
        recommendations.push('✅ <strong>Отличный темп!</strong> Команда завершает задачи эффективно.');
    }
    
    return recommendations.length > 0 
        ? '<ul>' + recommendations.map(r => '<li style="margin-bottom: 10px;">' + r + '</li>').join('') + '</ul>'
        : '<p>Всё идёт по плану! 🎯</p>';
}

function renderIssuesTable(issues) {
    const types = [...new Set(allIssues.map(i => i.issue_type).filter(Boolean))].sort();
    const statuses = [...new Set(allIssues.map(i => i.status).filter(Boolean))].sort();
    const priorities = [...new Set(allIssues.map(i => i.priority).filter(Boolean))].sort();
    const sprints = [...new Set(allIssues.map(i => i.sprint).filter(Boolean))].sort().reverse();
    
    const html = `
<div style="display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; align-items: center;">
    <select id="filterType" onchange="applyTableFilters()" style="padding: 10px; border-radius: 5px; border: 2px solid #e0e0e0;">
        <option value="">Все типы</option>
        ${types.map(t => `<option value="${t}">${t}</option>`).join('')}
    </select>
    <select id="filterStatus" onchange="applyTableFilters()" style="padding: 10px; border-radius: 5px; border: 2px solid #e0e0e0;">
        <option value="">Все статусы</option>
        ${statuses.map(s => `<option value="${s}">${s}</option>`).join('')}
    </select>
    <select id="filterPriority" onchange="applyTableFilters()" style="padding: 10px; border-radius: 5px; border: 2px solid #e0e0e0;">
        <option value="">Все приоритеты</option>
        ${priorities.map(p => `<option value="${p}">${p}</option>`).join('')}
    </select>
    <select id="filterSprint" onchange="applyTableFilters()" style="padding: 10px; border-radius: 5px; border: 2px solid #e0e0e0;">
        <option value="">Все спринты</option>
        ${sprints.map(s => `<option value="${s}">${s}</option>`).join('')}
    </select>
    <button onclick="clearTableFilters()" class="refresh-btn" style="padding: 10px 20px;">🔄 Сбросить фильтры</button>
</div>
<div class='issuesTable-container'>
    <table>
        <thead>
            <tr>
                <th onclick="sortTable('issue_key')" style="cursor: pointer;" title="Кликните для сортировки">Ключ ${getSortIcon('issue_key')}</th>
                <th style="cursor: default;">Тип</th>
                <th style="cursor: default;">Статус</th>
                <th onclick="sortTable('summary')" style="cursor: pointer;" title="Кликните для сортировки">Описание ${getSortIcon('summary')}</th>
                <th onclick="sortTable('assignee')" style="cursor: pointer;" title="Кликните для сортировки">Исполнитель ${getSortIcon('assignee')}</th>
                <th style="cursor: default;">Приоритет</th>
                <th onclick="sortTable('time_original_estimate')" style="cursor: pointer;" title="Кликните для сортировки">Оценка ${getSortIcon('time_original_estimate')}</th>
                <th onclick="sortTable('time_spent')" style="cursor: pointer;" title="Кликните для сортировки">Затрачено ${getSortIcon('time_spent')}</th>
                <th style="cursor: default;">Спринт</th>
                <th style="cursor: default;">Связи</th>
            </tr>
        </thead>
        <tbody>
            ${issues.map(issue => `
                <tr class="${getRowClass(issue.issue_type)}">
                    <td><a href="${getJiraIssueLink(issue.issue_key)}" class="issue-key" target="_blank">${issue.issue_key}</a></td>
                    <td>${issue.issue_type || '-'}</td>
                    <td><span class="badge ${getStatusClass(issue.status)}">${issue.status || '-'}</span></td>
                    <td>${issue.summary || '-'}</td>
                    <td>${issue.assignee || '-'}</td>
                    <td class="${getPriorityClass(issue.priority)}">${issue.priority || '-'}</td>
                    <td>${formatHours(issue.time_original_estimate)}</td>
                    <td>${formatHours(issue.time_spent)}</td>
                    <td>${issue.sprint || '-'}</td>
                    <td>${renderLinkedIssues(issue.linked_issues)}</td>
                </tr>
            `).join('')}
        </tbody>
    </table>
</div>`;
    document.getElementById('issuesTable').innerHTML = html;
}

function renderSprintsTable(sprints) {
    const sortedSprints = [...sprints].sort((a, b) => {
        const getSprintNumber = (sprintName) => {
            if (!sprintName) return 0;
            const match = sprintName.match(/#(\d+)/);
            return match ? parseInt(match[1]) : 0;
        };
        return getSprintNumber(b.sprint) - getSprintNumber(a.sprint);
    });

    const html = `
        <table>
            <thead>
                <tr>
                    <th>Спринт</th>
                    <th>Задач</th>
                    <th>Оценка (часы)</th>
                    <th>Затрачено (часы)</th>
                </tr>
            </thead>
            <tbody>
                ${sortedSprints.map(sprint => {
                    const formatSprintHours = (hours) => {
                        if (!hours) return '0';
                        const num = Number(hours);
                        return num % 1 === 0 ? num.toString() : num.toFixed(2);
                    };
                    return `
                        <tr>
                            <td>${sprint.sprint}</td>
                            <td>${sprint.count}</td>
                            <td>${formatSprintHours(sprint.total_estimate)}</td>
                            <td>${formatSprintHours(sprint.total_spent)}</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
    document.getElementById('sprintsTable').innerHTML = html;
}

function renderStatusTable(statuses) {
    const html = `
        <table>
            <thead>
                <tr>
                    <th>Статус</th>
                    <th>Количество</th>
                    <th>Процент</th>
                </tr>
            </thead>
            <tbody>
                ${statuses.map(status => {
                    const total = statuses.reduce((sum, s) => sum + s.count, 0);
                    const percent = ((status.count / total) * 100).toFixed(1);
                    return `
                        <tr>
                            <td><span class="badge ${getStatusClass(status.status)}">${status.status}</span></td>
                            <td>${status.count}</td>
                            <td>${percent}%</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
    document.getElementById('statusTable').innerHTML = html;
}

function renderLinkedIssues(linkedIssues) {
    if (!linkedIssues || linkedIssues.length === 0) return '-';
    return `
        <div class="linked-issues">
            ${linkedIssues.map(key => 
                `<a href="${getJiraIssueLink(key)}" target="_blank" class="linked-issue-badge" style="text-decoration: none;">${key}</a>`
            ).join('')}
        </div>
    `;
}

function getStatusClass(status) {
    if (!status) return 'badge-closed';
    const lower = status.toLowerCase();
    if (lower.includes('работ') || lower.includes('progress')) return 'badge-progress';
    if (lower.includes('готов') || lower.includes('done') || lower.includes('closed')) return 'badge-done';
    if (lower.includes('откр') || lower.includes('open') || lower.includes('new')) return 'badge-open';
    return 'badge-closed';
}

function getPriorityClass(priority) {
    if (!priority) return '';
    const lower = priority.toLowerCase();
    if (lower.includes('high') || lower.includes('высок')) return 'priority-high';
    if (lower.includes('medium') || lower.includes('средн')) return 'priority-medium';
    if (lower.includes('low') || lower.includes('низк')) return 'priority-low';
    return '';
}

function formatHours(hours) {
    if (hours === null || hours === undefined || hours === '' || hours === 'null') return '-';
    if (typeof hours === 'object') return '-';
    const num = Number(hours);
    if (isNaN(num) || !isFinite(num)) return '-';
    if (num % 1 === 0) return `${num}ч`;
    return `${num.toFixed(2)}ч`;
}

function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');
    
    if (tabName === 'links' && !network) {
        loadGraphVisualization();
    }
    if (tabName === 'sprintLoad') {
        loadSprintStats();
    }
}

function showIssueDetails(issueKey) {
    window.open(getJiraIssueLink(issueKey), '_blank');
}

document.addEventListener('DOMContentLoaded', () => {
    const searchBox = document.getElementById('searchBox');
    searchBox.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        let filtered = allIssues.filter(issue => {
            if (activeFilters.type && issue.issue_type !== activeFilters.type) return false;
            if (activeFilters.status && issue.status !== activeFilters.status) return false;
            if (activeFilters.priority && issue.priority !== activeFilters.priority) return false;
            if (activeFilters.sprint && issue.sprint !== activeFilters.sprint) return false;
            return true;
        });
        if (query) {
            filtered = filtered.filter(issue => 
                issue.issue_key.toLowerCase().includes(query) ||
                (issue.summary && issue.summary.toLowerCase().includes(query)) ||
                (issue.assignee && issue.assignee.toLowerCase().includes(query))
            );
        }
        if (sortColumn) {
            filtered = [...filtered].sort((a, b) => {
                let aVal = a[sortColumn];
                let bVal = b[sortColumn];
                if (aVal === null || aVal === undefined || aVal === '') aVal = '';
                if (bVal === null || bVal === undefined || bVal === '') bVal = '';
                if (sortColumn === 'time_original_estimate' || sortColumn === 'time_spent') {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                }
                if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
        }
        renderIssuesTable(filtered);
        if (document.getElementById('filterType')) {
            document.getElementById('filterType').value = activeFilters.type;
            document.getElementById('filterStatus').value = activeFilters.status;
            document.getElementById('filterPriority').value = activeFilters.priority;
            document.getElementById('filterSprint').value = activeFilters.sprint;
        }
    });
});

async function loadSEOTasks() {
    try {
        const response = await fetch('/api/my-tasks-seo');
        const tasks = await response.json();
        if (tasks.length === 0) {
            alert('SEO задач не найдено');
            return;
        }
        const html = `
            <h2>🔍 Мои SEO задачи (${tasks.length})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ключ</th>
                        <th>Описание</th>
                        <th>Статус</th>
                        <th>Затрачено</th>
                        <th>Спринт</th>
                    </tr>
                </thead>
                <tbody>
                    ${tasks.map(task => `
                        <tr>
                            <td><a href="${getJiraIssueLink(task.issue_key)}" class="issue-key" target="_blank">${task.issue_key}</a></td>
                            <td>${task.summary || '-'}</td>
                            <td><span class="badge ${getStatusClass(task.status)}">${task.status}</span></td>
                            <td>${formatHours(task.time_spent)}</td>
                            <td>${task.sprint || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        document.getElementById('issuesTable').innerHTML = html;
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка загрузки SEO задач');
    }
}

loadData();

async function loadGraphVisualization() {
    try {
        const response = await fetch('/api/graph');
        const data = await response.json();
        graphData = data;
        
        const nodes = data.nodes.map(node => {
            const tooltip = [
                `${node.issue_key}`,
                `Название: ${node.summary || '-'}`,
                `Статус: ${node.status || '-'}`,
                `Тип: ${node.issue_type || '-'}`,
                `Приоритет: ${node.priority || '-'}`,
                `Исполнитель: ${node.assignee || '-'}`
            ].join('\n');
            
            let shape = 'box';
            let borderWidth = 2;
            const issueType = (node.issue_type || '').toLowerCase();
            
            if (issueType.includes('epic') || issueType === 'эпик') {
                shape = 'hexagon';
                borderWidth = 3;
            } else if (issueType.includes('story') || issueType.includes('история')) {
                shape = 'ellipse';
                borderWidth = 2;
            } else {
                shape = 'box';
                borderWidth = 2;
            }
            
            return {
                id: node.issue_key,
                label: node.issue_key,
                title: tooltip,
                color: {
                    background: getNodeColor(node.status),
                    border: getNodeBorderColor(node.status),
                    highlight: {
                        background: getNodeColor(node.status),
                        border: '#667eea'
                    },
                    hover: {
                        background: getNodeColor(node.status),
                        border: '#667eea'
                    }
                },
                font: { size: 12, color: '#333', bold: true },
                shape: shape,
                margin: 10,
                borderWidth: borderWidth,
                borderWidthSelected: 4
            };
        });

        const edges = data.edges.map((edge, idx) => ({
            id: idx,
            from: edge.source_issue_key,
            to: edge.target_issue_key,
            label: edge.direction_label,
            arrows: 'to',
            color: edge.direction === 'inward' ? '#e74c3c' : '#3498db',
            font: { size: 9 },
            smooth: { type: 'curvedCW', roundness: 0.15 }
        }));

        renderGraph(nodes, edges);
        
    } catch (error) {
        console.error('Ошибка загрузки графа:', error);
        document.getElementById('linksTable').innerHTML = 
            '<p style="color: #e74c3c; text-align: center; padding: 50px;">Ошибка загрузки графа связей</p>';
    }
}

function getNodeColor(status) {
    if (!status) return '#dfe6e9';
    const s = status.toLowerCase();
    if (s.includes('готов') || s.includes('done')) return '#55efc4';
    if (s.includes('работ') || s.includes('progress')) return '#74b9ff';
    if (s.includes('откр') || s.includes('open')) return '#ffeaa7';
    return '#dfe6e9';
}

function getNodeBorderColor(status) {
    if (!status) return '#b2bec3';
    const s = status.toLowerCase();
    if (s.includes('готов') || s.includes('done')) return '#00b894';
    if (s.includes('работ') || s.includes('progress')) return '#0984e3';
    if (s.includes('откр') || s.includes('open')) return '#fdcb6e';
    return '#b2bec3';
}

function renderGraph(nodes, edges) {
    const container = document.getElementById('graphContainer');
    if (!container) {
        const linksDiv = document.getElementById('linksTable');
        linksDiv.innerHTML = `
            <div style="margin-bottom: 20px; display: flex; gap: 10px; align-items: center;">
                <button onclick="fitGraph()" class="refresh-btn">📐 По размеру экрана</button>
                <button onclick="toggleGraphPhysics()" class="refresh-btn">⚡ Физика: <span id="physicsStatus">ВКЛ</span></button>
                <div style="flex: 1;"></div>
                <div style="background: #f9f9f9; padding: 10px 20px; border-radius: 8px;">
                    <strong>Узлов:</strong> ${nodes.length} | <strong>Связей:</strong> ${edges.length}
                </div>
            </div>
            <div id="graphContainer" style="width: 100%; height: 600px; border: 2px solid #e0e0e0; border-radius: 10px;"></div>
            
            <div style="margin-top: 20px; background: #f9f9f9; padding: 15px; border-radius: 10px;">
                <h4 style="margin: 0 0 15px 0; color: #333;">Легенда:</h4>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <strong style="display: block; margin-bottom: 10px; color: #666;">Статусы (цвет):</strong>
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 24px; height: 24px; background: #55efc4; border: 2px solid #00b894; border-radius: 4px;"></div>
                                <span>Готово</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 24px; height: 24px; background: #74b9ff; border: 2px solid #0984e3; border-radius: 4px;"></div>
                                <span>В работе</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 24px; height: 24px; background: #ffeaa7; border: 2px solid #fdcb6e; border-radius: 4px;"></div>
                                <span>Открыто</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 24px; height: 24px; background: #dfe6e9; border: 2px solid #b2bec3; border-radius: 4px;"></div>
                                <span>Другое</span>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <strong style="display: block; margin-bottom: 10px; color: #666;">Типы задач (форма):</strong>
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="24" height="24" viewBox="0 0 24 24">
                                    <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" fill="#74b9ff" stroke="#0984e3" stroke-width="2"/>
                                </svg>
                                <span>Эпик (шестиугольник)</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="24" height="24" viewBox="0 0 24 24">
                                    <ellipse cx="12" cy="12" rx="10" ry="7" fill="#74b9ff" stroke="#0984e3" stroke-width="2"/>
                                </svg>
                                <span>История (овал)</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="24" height="24" viewBox="0 0 24 24">
                                    <rect x="4" y="7" width="16" height="10" fill="#74b9ff" stroke="#0984e3" stroke-width="2" rx="2"/>
                                </svg>
                                <span>Задача (прямоугольник)</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                    <strong style="display: block; margin-bottom: 10px; color: #666;">Связи:</strong>
                    <div style="display: flex; gap: 20px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 30px; height: 3px; background: #e74c3c;"></div>
                            <span>Входящая связь</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 30px; height: 3px; background: #3498db;"></div>
                            <span>Исходящая связь</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    const graphContainer = document.getElementById('graphContainer');
    
    const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };

    const options = {
        nodes: {
            shape: 'box',
            margin: 8,
            widthConstraint: { maximum: 120 }
        },
        edges: {
            smooth: { type: 'curvedCW', roundness: 0.15 },
            arrows: { to: { enabled: true, scaleFactor: 0.4 } }
        },
        physics: {
            enabled: true,
            stabilization: { iterations: 200 },
            barnesHut: {
                gravitationalConstant: -10000,
                springConstant: 0.04,
                springLength: 150
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            hideEdgesOnDrag: false,
            hideEdgesOnZoom: false,
            navigationButtons: true,
            keyboard: true
        },
        layout: {
            improvedLayout: true
        }
    };

    if (network) {
        network.destroy();
    }

    network = new vis.Network(graphContainer, data, options);

    let tooltipDiv = document.getElementById('graphTooltip');
    if (!tooltipDiv) {
        tooltipDiv = document.createElement('div');
        tooltipDiv.id = 'graphTooltip';
        tooltipDiv.style.cssText = `
            position: absolute;
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.6;
            pointer-events: none;
            z-index: 9999;
            display: none;
            max-width: 350px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            white-space: pre-line;
        `;
        document.body.appendChild(tooltipDiv);
    }

    network.on('hoverNode', function(params) {
        const nodeId = params.node;
        const node = nodes.find(n => n.id === nodeId);
        if (node && node.title) {
            tooltipDiv.innerHTML = node.title.replace(/\n/g, '<br>');
            tooltipDiv.style.display = 'block';
        }
    });

    network.on('blurNode', function() {
        tooltipDiv.style.display = 'none';
    });

    graphContainer.addEventListener('mousemove', function(e) {
        if (tooltipDiv.style.display === 'block') {
            tooltipDiv.style.left = (e.pageX + 15) + 'px';
            tooltipDiv.style.top = (e.pageY + 15) + 'px';
        }
    });

    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            showIssueDetails(nodeId);
        }
    });
}

function fitGraph() {
    if (network) {
        network.fit({ animation: { duration: 1000, easingFunction: 'easeInOutQuad' } });
    }
}

function toggleGraphPhysics() {
    if (network) {
        const currentPhysics = network.physics.options.enabled;
        network.setOptions({ physics: { enabled: !currentPhysics } });
        document.getElementById('physicsStatus').textContent = !currentPhysics ? 'ВКЛ' : 'ВЫКЛ';
    }
}

async function loadCurrentSprintIssues() {
    try {
        const response = await fetch('/api/current-sprint-issues');
        const data = await response.json();
        
        if (data.error || !data.issues || data.issues.length === 0) {
            document.getElementById('sprintIssuesTable').innerHTML = 
                '<p style="text-align: center; color: #999; padding: 20px;">Нет задач в текущем спринте</p>';
            return;
        }
        
        renderSprintIssuesTable(data.issues, data.sprint_name);
        
    } catch (error) {
        console.error('Ошибка загрузки задач спринта:', error);
        document.getElementById('sprintIssuesTable').innerHTML = 
            '<p style="text-align: center; color: #e74c3c; padding: 20px;">Ошибка загрузки задач</p>';
    }
}

function renderSprintIssuesTable(issues, sprintName) {
    const byStatus = {
        'В работе': [],
        'Открыто': [],
        'Готово': [],
        'Другое': []
    };
    
    issues.forEach(issue => {
        const status = issue.status || 'Другое';
        if (byStatus[status]) {
            byStatus[status].push(issue);
        } else {
            byStatus['Другое'].push(issue);
        }
    });
    
    let html = `
        <div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3>📋 Задачи спринта: ${sprintName}</h3>
            <p style="color: #666;">Всего задач: ${issues.length}</p>
        </div>
    `;
    
    for (const [status, statusIssues] of Object.entries(byStatus)) {
        if (statusIssues.length === 0) continue;
        
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #e0e0e0;">
                    <span class="badge ${getStatusClass(status)}">${status}</span>
                    <span style="color: #999; font-size: 0.9em; margin-left: 10px;">(${statusIssues.length})</span>
                </h3>
                <div class='issuesTable-container'>
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 100px;">Ключ</th>
                                <th style="width: 100px;">Тип</th>
                                <th>Описание</th>
                                <th style="width: 150px;">Исполнитель</th>
                                <th style="width: 100px;">Приоритет</th>
                                <th style="width: 80px;">Оценка</th>
                                <th style="width: 80px;">Затрачено</th>
                                <th style="width: 100px;">Связи</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${statusIssues.map(issue => `
                                <tr class="${getRowClass(issue.issue_type)}">
                                    <td><a href="${getJiraIssueLink(issue.issue_key)}" class="issue-key" target="_blank">${issue.issue_key}</a></td>
                                    <td>${issue.issue_type || '-'}</td>
                                    <td>${issue.summary || '-'}</td>
                                    <td>${issue.assignee || '-'}</td>
                                    <td class="${getPriorityClass(issue.priority)}">${issue.priority || '-'}</td>
                                    <td>${formatHours(issue.time_original_estimate)}</td>
                                    <td>${formatHours(issue.time_spent)}</td>
                                    <td>${renderLinkedIssues(issue.linked_issues)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    document.getElementById('sprintIssuesTable').innerHTML = html;
}