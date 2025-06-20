let allStudents = [];
let filteredStudents = [];
let assignments = [];

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function () {
    loadGrades();
    setupSearch();
});

// Load grades from API
async function loadGrades() {
    try {
        const response = await fetch('/api/grades-table');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        allStudents = data.students || [];
        filteredStudents = [...allStudents];
        extractAssignments();
        renderTable();
        updateSearchStats();
    } catch (error) {
        console.error('Error loading grades:', error);
        showError('Failed to load grades. Please refresh the page.');
    }
}

// Extract unique assignments from student data
function extractAssignments() {
    const assignmentMap = new Map();
    allStudents.forEach(student => {
        student.grades.forEach(grade => {
            const key = `${grade.assignment}|${grade.date}`;
            if (!assignmentMap.has(key)) {
                assignmentMap.set(key, {
                    name: grade.assignment,
                    date: grade.date,
                    max_points: grade.max_points
                });
            }
        });
    });
    assignments = Array.from(assignmentMap.values());
    assignments.sort((a, b) => {
        if (a.date && b.date) return new Date(a.date) - new Date(b.date);
        return a.name.localeCompare(b.name);
    });
}

// Render the complete table
function renderTable() {
    renderHeader();
    renderBody();
}

// Render table header
function renderHeader() {
    const headerRow = document.getElementById('tableHeader');
    headerRow.innerHTML = '<th class="student-info">Student</th>';
    assignments.forEach(assignment => {
        const th = document.createElement('th');
        th.className = 'assignment-header';
        th.innerHTML = `
            <div class="assignment-name">${escapeHtml(assignment.name)}</div>
            <div class="assignment-info">
                ${assignment.date ? formatDate(assignment.date) : 'No date'} | 
                ${assignment.max_points} pts
            </div>
        `;
        headerRow.appendChild(th);
    });
}

// Render table body
function renderBody() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    if (filteredStudents.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="${assignments.length + 1}" class="no-results">
            ${allStudents.length === 0 ? 'No students found in database.' : 'No students match your search.'}
        </td>`;
        tbody.appendChild(row);
        return;
    }

    filteredStudents.forEach(student => {
        const row = document.createElement('tr');
        const studentCell = document.createElement('td');
        studentCell.className = 'student-info';
        studentCell.innerHTML = `
            <div class="student-name">${highlightText(escapeHtml(`${student.last_name}, ${student.first_name}`))}</div>
            <div class="student-email">${highlightText(escapeHtml(student.email))}</div>
        `;
        row.appendChild(studentCell);

        assignments.forEach(assignment => {
            const gradeCell = document.createElement('td');
            gradeCell.className = 'grade-cell';
            const grade = student.grades.find(g => g.assignment === assignment.name && g.date === assignment.date);
            if (grade) {
                const percentage = Math.round((grade.score / grade.max_points) * 100);
                // Here is your active grade-good / grade-medium / grade-poor logic:
                const gradeClass = percentage >= 80 ? 'grade-good' : 
                                   percentage >= 60 ? 'grade-medium' : 'grade-poor';
                gradeCell.innerHTML = `
                    <div class="grade-score ${gradeClass}">${grade.score}/${grade.max_points}</div>
                    <div class="grade-percentage">${percentage}%</div>
                `;
            } else {
                gradeCell.innerHTML = '<div class="no-grade">—</div>';
            }
            row.appendChild(gradeCell);
        });

        tbody.appendChild(row);
    });
}

// Setup search functionality
function setupSearch() {
    const searchInput = document.getElementById('studentSearch');
    const clearButton = document.getElementById('clearSearch');

    searchInput.addEventListener('input', function () {
        const query = this.value.trim();
        if (query) {
            filterStudents(query);
            clearButton.style.display = 'inline-block';
        } else {
            clearSearch();
        }
    });

    clearButton.addEventListener('click', clearSearch);

    searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') e.preventDefault();
    });
}

// Filter students based on search query
function filterStudents(query) {
    const searchTerm = query.toLowerCase();
    filteredStudents = allStudents.filter(student => {
        const fullName = `${student.first_name} ${student.last_name}`.toLowerCase();
        const reverseName = `${student.last_name}, ${student.first_name}`.toLowerCase();
        const email = student.email.toLowerCase();
        return fullName.includes(searchTerm) || reverseName.includes(searchTerm) || email.includes(searchTerm);
    });
    renderBody();
    updateSearchStats();
}

// Clear search
function clearSearch() {
    document.getElementById('studentSearch').value = '';
    document.getElementById('clearSearch').style.display = 'none';
    filteredStudents = [...allStudents];
    renderBody();
    updateSearchStats();
}

// Update search statistics
function updateSearchStats() {
    const statsElement = document.getElementById('searchStats');
    const searchInput = document.getElementById('studentSearch');
    if (searchInput.value.trim()) {
        statsElement.textContent = `Showing ${filteredStudents.length} of ${allStudents.length} students`;
    } else {
        statsElement.textContent = `${allStudents.length} students total`;
    }
}

// Highlight search terms in text
function highlightText(text) {
    const searchTerm = document.getElementById('studentSearch').value.trim();
    if (!searchTerm) return text;
    const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// Utility functions
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function formatDate(dateString) {
    if (!dateString) return 'No date';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Optionally, you can remove this old getGradeClass function or keep it commented out:
/*
function getGradeClass(percentage) {
    if (percentage >= 90) return 'grade-A';
    if (percentage >= 80) return 'grade-B';
    if (percentage >= 70) return 'grade-C';
    if (percentage >= 60) return 'grade-D';
    return 'grade-F';
}
*/

function showError(message) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="${assignments.length + 1}" class="error">
                ${escapeHtml(message)}
            </td>
        </tr>
    `;
}

// Optional: Refresh data every 5 minutes
setInterval(loadGrades, 300000);
