// shared-utils.js - Common utilities for grade system
class GradeUtils {
    static escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    static escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    static formatDate(dateString) {
        if (!dateString) return 'No date';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    static isValidEmail(email) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(email);
    }

    static getGradeClass(percentage) {
        if (percentage >= 80) return 'grade-good';
        if (percentage >= 60) return 'grade-medium';
        return 'grade-poor';
    }

    static getGradeLetter(percentage) {
        if (percentage >= 90) return 'A';
        if (percentage >= 80) return 'B';
        if (percentage >= 70) return 'C';
        if (percentage >= 60) return 'D';
        return 'F';
    }

    static calculatePercentage(score, maxPoints) {
        return maxPoints > 0 ? Math.round((score / maxPoints) * 100) : 0;
    }

    static async fetchWithErrorHandling(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    static showError(containerId, message, colSpan = 1) {
        const container = document.getElementById(containerId);
        if (container.tagName === 'TBODY') {
            container.innerHTML = `
                <tr>
                    <td colspan="${colSpan}" class="error">
                        ${this.escapeHtml(message)}
                    </td>
                </tr>
            `;
        } else {
            container.innerHTML = `
                <div class="error">
                    <strong>Error:</strong> ${this.escapeHtml(message)}
                </div>
            `;
            container.style.display = 'block';
        }
    }
}

// grades-table.js - Enhanced grades table with tag search
class GradesTable {
    constructor() {
        this.allStudents = [];
        this.filteredStudents = [];
        this.assignments = [];
        this.currentStudentSearch = '';
        this.currentTagSearch = '';
        this.visibleColumns = new Set();
        this.init();
    }

    init() {
        this.loadGrades();
        this.setupSearch();
        this.setupTagSearch();
    }

    async loadGrades() {
        try {
            const data = await GradeUtils.fetchWithErrorHandling('/api/grades-table');
            this.allStudents = data.students || [];
            this.filteredStudents = [...this.allStudents];
            this.extractAssignments();
            this.renderTable();
            this.updateSearchStats();
        } catch (error) {
            console.error('Error loading grades:', error);
            GradeUtils.showError('tableBody', 'Failed to load grades. Please refresh the page.', this.assignments.length + 1);
        }
    }

    extractAssignments() {
        const assignmentMap = new Map();
        this.allStudents.forEach(student => {
            student.grades.forEach(grade => {
                const key = `${grade.assignment}|${grade.date}`;
                if (!assignmentMap.has(key)) {
                    assignmentMap.set(key, {
                        name: grade.assignment,
                        date: grade.date,
                        max_points: grade.max_points,
                        tags: grade.tags || [] // Assuming your grade data includes tags
                    });
                }
            });
        });
        this.assignments = Array.from(assignmentMap.values());
        this.assignments.sort((a, b) => {
            if (a.date && b.date) return new Date(a.date) - new Date(b.date);
            return a.name.localeCompare(b.name);
        });
        
        // Initialize all columns as visible
        this.visibleColumns = new Set(this.assignments.map((_, index) => index));
    }

    setupSearch() {
        const searchInput = document.getElementById('studentSearch');
        const clearButton = document.getElementById('clearSearch');

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const query = searchInput.value.trim();
                this.currentStudentSearch = query;
                this.applyFilters();
                if (query) {
                    clearButton.style.display = 'inline-block';
                } else {
                    clearButton.style.display = 'none';
                }
            });
        }

        if (clearButton) {
            clearButton.addEventListener('click', () => this.clearStudentSearch());
        }

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') e.preventDefault();
            });
        }
    }

    setupTagSearch() {
        // Create tag search input if it doesn't exist
        const searchContainer = document.querySelector('.search-container') || document.querySelector('.controls');
        if (searchContainer && !document.getElementById('tagSearch')) {
            const tagSearchHTML = `
                <div class="search-group">
                    <label for="tagSearch">Filter by Assignment Tag:</label>
                    <input type="text" id="tagSearch" placeholder="Enter tag to filter assignments..." />
                    <button type="button" id="clearTagSearch" style="display: none;">Clear</button>
                </div>
            `;
            searchContainer.insertAdjacentHTML('beforeend', tagSearchHTML);
        }

        const tagSearchInput = document.getElementById('tagSearch');
        const clearTagButton = document.getElementById('clearTagSearch');

        if (tagSearchInput) {
            tagSearchInput.addEventListener('input', () => {
                const query = tagSearchInput.value.trim();
                this.currentTagSearch = query;
                this.applyTagFilter();
                if (query) {
                    clearTagButton.style.display = 'inline-block';
                } else {
                    clearTagButton.style.display = 'none';
                }
            });
        }

        if (clearTagButton) {
            clearTagButton.addEventListener('click', () => this.clearTagSearch());
        }
    }

    applyFilters() {
        // Apply student name/email filter
        if (this.currentStudentSearch) {
            const searchTerm = this.currentStudentSearch.toLowerCase();
            this.filteredStudents = this.allStudents.filter(student => {
                const fullName = `${student.first_name} ${student.last_name}`.toLowerCase();
                const reverseName = `${student.last_name}, ${student.first_name}`.toLowerCase();
                const email = student.email.toLowerCase();
                return fullName.includes(searchTerm) || reverseName.includes(searchTerm) || email.includes(searchTerm);
            });
        } else {
            this.filteredStudents = [...this.allStudents];
        }
        
        this.renderBody();
        this.updateSearchStats();
    }

    applyTagFilter() {
        if (!this.currentTagSearch) {
            // Show all columns
            this.visibleColumns = new Set(this.assignments.map((_, index) => index));
        } else {
            // Filter columns by tag
            const searchTerm = this.currentTagSearch.toLowerCase();
            this.visibleColumns = new Set();
            
            this.assignments.forEach((assignment, index) => {
                // Check if assignment name contains the search term
                if (assignment.name.toLowerCase().includes(searchTerm)) {
                    this.visibleColumns.add(index);
                }
                // Check if any tags contain the search term
                if (assignment.tags && assignment.tags.some(tag => 
                    tag.toLowerCase().includes(searchTerm))) {
                    this.visibleColumns.add(index);
                }
            });
        }
        
        this.renderTable();
        this.updateSearchStats();
    }

    renderTable() {
        this.renderHeader();
        this.renderBody();
    }

    renderHeader() {
        const headerRow = document.getElementById('tableHeader');
        headerRow.innerHTML = '<th class="student-info">Student</th>';
        
        this.assignments.forEach((assignment, index) => {
            const th = document.createElement('th');
            th.className = 'assignment-header';
            th.style.display = this.visibleColumns.has(index) ? '' : 'none';
            
            const tagsHTML = assignment.tags && assignment.tags.length > 0 
                ? `<div class="assignment-tags">${assignment.tags.map(tag => 
                    `<span class="tag">${GradeUtils.escapeHtml(tag)}</span>`).join('')}</div>`
                : '';
            
            th.innerHTML = `
                <div class="assignment-name">${GradeUtils.escapeHtml(assignment.name)}</div>
                <div class="assignment-info">
                    ${assignment.date ? GradeUtils.formatDate(assignment.date) : 'No date'} | 
                    ${assignment.max_points} pts
                </div>
                ${tagsHTML}
            `;
            headerRow.appendChild(th);
        });
    }

    renderBody() {
        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = '';
        
        if (this.filteredStudents.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="${this.assignments.length + 1}" class="no-results">
                ${this.allStudents.length === 0 ? 'No students found in database.' : 'No students match your search.'}
            </td>`;
            tbody.appendChild(row);
            return;
        }

        this.filteredStudents.forEach(student => {
            const row = this.createStudentRow(student);
            tbody.appendChild(row);
        });
    }

    createStudentRow(student) {
        const row = document.createElement('tr');
        
        // Add interactivity
        row.style.cursor = 'pointer';
        row.classList.add('clickable-row');
        row.addEventListener('click', () => this.navigateToStudent(student));

        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#d4edda';
            this.style.transition = 'background-color 0.2s ease';
        });

        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });

        // Student info cell
        const studentCell = document.createElement('td');
        studentCell.className = 'student-info';
        studentCell.innerHTML = `
            <div class="student-name">${this.highlightText(GradeUtils.escapeHtml(`${student.last_name}, ${student.first_name}`))}</div>
            <div class="student-email">${this.highlightText(GradeUtils.escapeHtml(student.email))}</div>
        `;
        row.appendChild(studentCell);

        // Grade cells
        this.assignments.forEach((assignment, index) => {
            const gradeCell = this.createGradeCell(student, assignment);
            gradeCell.style.display = this.visibleColumns.has(index) ? '' : 'none';
            row.appendChild(gradeCell);
        });

        return row;
    }

    createGradeCell(student, assignment) {
        const gradeCell = document.createElement('td');
        gradeCell.className = 'grade-cell';
        const grade = student.grades.find(g => g.assignment === assignment.name && g.date === assignment.date);
        
        if (grade) {
            const percentage = GradeUtils.calculatePercentage(grade.score, grade.max_points);
            const gradeClass = GradeUtils.getGradeClass(percentage);
            gradeCell.innerHTML = `
                <div class="grade-score ${gradeClass}">${grade.score}/${grade.max_points}</div>
                <div class="grade-percentage">${percentage}%</div>
            `;
        } else {
            gradeCell.innerHTML = '<div class="no-grade">—</div>';
        }
        
        return gradeCell;
    }

    navigateToStudent(student) {
        if (student.email) {
            window.location.href = `/teacher-student-view?email=${encodeURIComponent(student.email)}`;
        } else {
            console.error('Student email not found:', student);
            alert('Unable to navigate to student profile - email not found.');
        }
    }

    clearStudentSearch() {
        const searchInput = document.getElementById('studentSearch');
        if (searchInput) {
            searchInput.value = '';
        }
        document.getElementById('clearSearch').style.display = 'none';
        this.currentStudentSearch = '';
        this.applyFilters();
    }

    clearTagSearch() {
        const tagSearchInput = document.getElementById('tagSearch');
        if (tagSearchInput) {
            tagSearchInput.value = '';
        }
        document.getElementById('clearTagSearch').style.display = 'none';
        this.currentTagSearch = '';
        this.applyTagFilter();
    }

    updateSearchStats() {
        const statsElement = document.getElementById('searchStats');
        if (statsElement) {
            const visibleAssignments = this.visibleColumns.size;
            const totalAssignments = this.assignments.length;
            
            let statusText = '';
            if (this.currentStudentSearch || this.currentTagSearch) {
                const parts = [];
                if (this.currentStudentSearch) {
                    parts.push(`${this.filteredStudents.length} of ${this.allStudents.length} students`);
                }
                if (this.currentTagSearch) {
                    parts.push(`${visibleAssignments} of ${totalAssignments} assignments`);
                }
                statusText = `Showing ${parts.join(', ')}`;
            } else {
                statusText = `${this.allStudents.length} students, ${totalAssignments} assignments`;
            }
            
            statsElement.textContent = statusText;
        }
    }

    highlightText(text) {
        const searchTerm = this.currentStudentSearch;
        if (!searchTerm) return text;
        const regex = new RegExp(`(${GradeUtils.escapeRegex(searchTerm)})`, 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }
}

// student-portal.js - Student portal (unchanged)
class StudentGradePortal {
    constructor() {
        this.emailInput = document.getElementById('emailInput');
        this.searchBtn = document.getElementById('searchBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.resultsSection = document.getElementById('resultsSection');
        this.searchStats = document.getElementById('searchStats');
        this.init();
    }

    init() {
        this.bindEvents();
        this.handleURLParams();
    }

    bindEvents() {
        this.searchBtn.addEventListener('click', () => this.searchGrades());
        this.clearBtn.addEventListener('click', () => this.clearResults());
        
        this.emailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchGrades();
        });

        this.emailInput.addEventListener('input', () => {
            if (this.emailInput.value.trim() === '') this.clearResults();
        });
    }

    handleURLParams() {
        const params = new URLSearchParams(window.location.search);
        const emailFromURL = params.get('email');
        if (emailFromURL) {
            this.emailInput.value = decodeURIComponent(emailFromURL);
            this.searchGrades();
        }
    }

    clearResults() {
        this.resultsSection.style.display = 'none';
        this.clearBtn.style.display = 'none';
        this.searchStats.style.display = 'none';
        this.emailInput.value = '';
        this.emailInput.focus();
    }

    async searchGrades() {
        const email = this.emailInput.value.trim();
        
        if (!email) {
            this.showError('Please enter your email address.');
            return;
        }

        if (!GradeUtils.isValidEmail(email)) {
            this.showError('Please enter a valid email address.');
            return;
        }

        try {
            this.showLoading();
            this.searchBtn.disabled = true;
            this.clearBtn.style.display = 'inline-block';
            
            const response = await fetch(`/api/student/${encodeURIComponent(email)}`);
            
            if (response.status === 404) {
                this.showNotFound(email);
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const studentData = await response.json();
            this.displayStudentGrades(studentData);
            
        } catch (error) {
            console.error('Error fetching student grades:', error);
            this.showError('Unable to fetch grades. Please try again later.');
        } finally {
            this.searchBtn.disabled = false;
        }
    }

    displayStudentGrades(student) {
        const overallPercentage = student.overall_percentage || 0;
        const gradeClass = GradeUtils.getGradeClass(overallPercentage);
        const gradeLetter = GradeUtils.getGradeLetter(overallPercentage);
        
        const gradesTableHtml = student.grades && student.grades.length > 0 
            ? this.generateGradesTable(student.grades)
            : '<p class="no-data">No assignments found.</p>';

        this.searchStats.textContent = `Found ${student.total_assignments || 0} assignments for ${student.first_name} ${student.last_name}`;
        this.searchStats.style.display = 'block';

        this.resultsSection.innerHTML = `
            <div class="student-header">
                <div class="student-name">${GradeUtils.escapeHtml(student.first_name)} ${GradeUtils.escapeHtml(student.last_name)}</div>
                <div class="student-email">${GradeUtils.escapeHtml(student.email)}</div>
                
                <div class="overall-stats">
                    <div class="stat-box">
                        <span class="stat-value">${student.total_assignments || 0}</span>
                        <div class="stat-label">Total Assignments</div>
                    </div>
                    <div class="stat-box">
                        <span class="stat-value">${student.total_points || 0}</span>
                        <div class="stat-label">Points Earned</div>
                    </div>
                    <div class="stat-box">
                        <span class="stat-value">${student.max_possible || 0}</span>
                        <div class="stat-label">Points Possible</div>
                    </div>
                </div>
                
                <div class="overall-grade ${gradeClass}">
                    Overall Grade: ${overallPercentage.toFixed(1)}% (${gradeLetter})
                </div>
            </div>
            
            <div class="grades-table-container">
                ${gradesTableHtml}
            </div>
        `;

        this.resultsSection.style.display = 'block';
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    generateGradesTable(grades) {
        const tableRows = grades.map(grade => {
            const percentage = GradeUtils.calculatePercentage(grade.score, grade.max_points);
            const gradeClass = GradeUtils.getGradeClass(percentage);
            const date = grade.date ? GradeUtils.formatDate(grade.date) : 'No date';
            
            return `
                <tr>
                    <td>
                        <div class="assignment-name">${GradeUtils.escapeHtml(grade.assignment)}</div>
                        <div class="assignment-date">${date}</div>
                    </td>
                    <td class="score-cell">${grade.score} / ${grade.max_points}</td>
                    <td class="percentage-cell">
                        <span class="percentage-badge ${gradeClass}">
                            ${percentage.toFixed(1)}%
                        </span>
                    </td>
                </tr>
            `;
        }).join('');

        return `
            <table class="grades-table">
                <thead>
                    <tr>
                        <th>Assignment</th>
                        <th style="text-align: center;">Score</th>
                        <th style="text-align: center;">Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
            </table>
        `;
    }

    showLoading() {
        this.resultsSection.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                Loading your grades...
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }

    showError(message) {
        GradeUtils.showError('resultsSection', message);
    }

    showNotFound(email) {
        this.resultsSection.innerHTML = `
            <div class="not-found">
                <h3>Student Not Found</h3>
                <p>No student found with email address: <strong>${GradeUtils.escapeHtml(email)}</strong></p>
                <p>Please check your email address and try again.</p>
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }
}


 // Enhanced search functionality for both students and tags
    document.addEventListener('DOMContentLoaded', function() {
        const studentSearchInput = document.getElementById('studentSearch');
        const tagSearchInput = document.getElementById('tagSearch');
        const clearStudentButton = document.getElementById('clearStudentSearch');
        const clearTagButton = document.getElementById('clearTagSearch');
        const searchStats = document.getElementById('searchStats');
        
        let currentStudentFilter = '';
        let currentTagFilter = '';
        let allAssignmentColumns = [];
        
        // Store column information when table loads
        function initializeColumnData() {
            const headerRow = document.getElementById('tableHeader');
            const headers = Array.from(headerRow.children).slice(1); // Skip student column
            
            allAssignmentColumns = headers.map((header, index) => ({
                index: index + 1, // +1 because we skip student column
                element: header,
                name: header.textContent.toLowerCase(),
                tags: (header.getAttribute('data-tags') || '').toLowerCase().split(',').filter(tag => tag.trim())
            }));
        }
        
        // Enhanced student search
        function performStudentSearch(searchTerm) {
            const lowerSearchTerm = searchTerm.toLowerCase();
            const tableBody = document.getElementById('tableBody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            
            let visibleStudents = 0;
            
            rows.forEach(row => {
                const studentCell = row.querySelector('.student-info, td:first-child');
                if (!studentCell) return;
                
                const studentText = studentCell.textContent.toLowerCase();
                const hasMatch = !searchTerm || studentText.includes(lowerSearchTerm);
                
                if (hasMatch) {
                    row.classList.remove('student-filtered');
                    visibleStudents++;
                    
                    // Highlight matching text
                    if (searchTerm) {
                        studentCell.classList.add('highlighted-student');
                    } else {
                        studentCell.classList.remove('highlighted-student');
                    }
                } else {
                    row.classList.add('student-filtered');
                    studentCell.classList.remove('highlighted-student');
                }
            });
            
            updateRowVisibility();
            updateSearchStats();
        }
        
        // Enhanced tag/assignment search
        function performTagSearch(searchTerm) {
            if (!searchTerm.trim()) {
                // Show all columns
                allAssignmentColumns.forEach(col => {
                    col.element.classList.remove('column-hidden');
                    showColumnInRows(col.index);
                });
                updateSearchStats();
                return;
            }
            
            const lowerSearchTerm = searchTerm.toLowerCase();
            let visibleColumns = 0;
            
            allAssignmentColumns.forEach(col => {
                const nameMatches = col.name.includes(lowerSearchTerm);
                const tagMatches = col.tags.some(tag => tag.includes(lowerSearchTerm));
                
                if (nameMatches || tagMatches) {
                    col.element.classList.remove('column-hidden');
                    col.element.classList.add('highlighted-assignment');
                    showColumnInRows(col.index);
                    visibleColumns++;
                } else {
                    col.element.classList.add('column-hidden');
                    col.element.classList.remove('highlighted-assignment');
                    hideColumnInRows(col.index);
                }
            });
            
            updateSearchStats();
        }
        
        function showColumnInRows(columnIndex) {
            const tableBody = document.getElementById('tableBody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            
            rows.forEach(row => {
                const cell = row.children[columnIndex];
                if (cell) {
                    cell.classList.remove('column-hidden');
                }
            });
        }
        
        function hideColumnInRows(columnIndex) {
            const tableBody = document.getElementById('tableBody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            
            rows.forEach(row => {
                const cell = row.children[columnIndex];
                if (cell) {
                    cell.classList.add('column-hidden');
                }
            });
        }
        
        function updateRowVisibility() {
            const tableBody = document.getElementById('tableBody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            
            rows.forEach(row => {
                const isStudentFiltered = row.classList.contains('student-filtered');
                row.style.display = isStudentFiltered ? 'none' : '';
            });
        }
        
        function updateSearchStats() {
            const tableBody = document.getElementById('tableBody');
            const visibleRows = Array.from(tableBody.querySelectorAll('tr')).filter(row => 
                row.style.display !== 'none' && !row.querySelector('.loading')
            ).length;
            
            const visibleColumns = allAssignmentColumns.filter(col => 
                !col.element.classList.contains('column-hidden')
            ).length;
            
            let statsText = '';
            if (currentStudentFilter || currentTagFilter) {
                const parts = [];
                if (currentStudentFilter) {
                    parts.push(`${visibleRows} student(s)`);
                }
                if (currentTagFilter) {
                    parts.push(`${visibleColumns} assignment(s)`);
                }
                statsText = `Showing: ${parts.join(', ')}`;
            } else {
                statsText = `${visibleRows} students, ${allAssignmentColumns.length} assignments`;
            }
            
            searchStats.textContent = statsText;
        }
        
        function clearStudentSearch() {
            studentSearchInput.value = '';
            clearStudentButton.style.display = 'none';
            currentStudentFilter = '';
            
            // Remove student filtering
            const tableBody = document.getElementById('tableBody');
            const rows = Array.from(tableBody.querySelectorAll('tr'));
            rows.forEach(row => {
                row.classList.remove('student-filtered');
                const studentCell = row.querySelector('.student-info, td:first-child');
                if (studentCell) {
                    studentCell.classList.remove('highlighted-student');
                }
            });
            
            updateRowVisibility();
            updateSearchStats();
            studentSearchInput.focus();
        }
        
        function clearTagSearch() {
            tagSearchInput.value = '';
            clearTagButton.style.display = 'none';
            currentTagFilter = '';
            
            // Show all columns
            allAssignmentColumns.forEach(col => {
                col.element.classList.remove('column-hidden', 'highlighted-assignment');
                showColumnInRows(col.index);
            });
            
            updateSearchStats();
            tagSearchInput.focus();
        }
        
        // Event listeners
        studentSearchInput.addEventListener('input', function() {
            currentStudentFilter = this.value.trim();
            
            if (currentStudentFilter) {
                clearStudentButton.style.display = 'inline-block';
            } else {
                clearStudentButton.style.display = 'none';
            }
            
            performStudentSearch(currentStudentFilter);
        });
        
        tagSearchInput.addEventListener('input', function() {
            currentTagFilter = this.value.trim();
            
            if (currentTagFilter) {
                clearTagButton.style.display = 'inline-block';
            } else {
                clearTagButton.style.display = 'none';
            }
            
            performTagSearch(currentTagFilter);
        });
        
        clearStudentButton.addEventListener('click', clearStudentSearch);
        clearTagButton.addEventListener('click', clearTagSearch);
        
        // Initialize when table is loaded
        // You'll need to call this after your existing table loading logic
        function initializeSearch() {
            initializeColumnData();
            updateSearchStats();
        }
        
        // Wait for table to load, then initialize
        // Adjust this timing based on your existing code
        const checkTableLoaded = setInterval(() => {
            const tableBody = document.getElementById('tableBody');
            const loadingCell = tableBody.querySelector('.loading');
            
            if (!loadingCell) {
                clearInterval(checkTableLoaded);
                initializeSearch();
            }
        }, 500);
        
        // Expose functions for external use if needed
        window.gradeSearchFunctions = {
            initializeSearch,
            performStudentSearch,
            performTagSearch
        };
    });

// Initialize based on page type
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tableHeader')) {
        // Grades table page
        const gradesTable = new GradesTable();
        // Optional: Refresh data every 5 minutes
        setInterval(() => gradesTable.loadGrades(), 300000);
    } else if (document.getElementById('emailInput')) {
        // Student portal page
        new StudentGradePortal();
    }
});

//NEW FUNCTIONS FOR NEW MAIN.PY
// Add this JavaScript to your existing dashboard.html template
// or create a separate static/js/dashboard.js file and include it

// Tenant ID management for API calls
const TenantManager = {
    getTenantId() {
        return localStorage.getItem('tenantId');
    },

    setTenantId(tenantId) {
        localStorage.setItem('tenantId', tenantId);
    },

    clearTenantId() {
        localStorage.removeItem('tenantId');
    },

    // Redirect to tenant selection if no tenant ID
    checkTenantId() {
        const tenantId = this.getTenantId();
        if (!tenantId) {
            window.location.href = '/';
            return false;
        }
        return tenantId;
    },

    // Get headers with tenant ID for API calls
    getHeaders() {
        const tenantId = this.getTenantId();
        return {
            'Content-Type': 'application/json',
            'X-Tenant-ID': tenantId || ''
        };
    }
};

// Enhanced fetch function that automatically includes tenant headers
async function tenantFetch(url, options = {}) {
    const tenantId = TenantManager.checkTenantId();
    if (!tenantId) return; // Will redirect to tenant selection

    const defaultHeaders = TenantManager.getHeaders();
    
    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, config);
        
        // If unauthorized or tenant error, redirect to tenant selection
        if (response.status === 400 || response.status === 401) {
            const errorData = await response.json().catch(() => ({}));
            if (errorData.detail && errorData.detail.includes('tenant')) {
                TenantManager.clearTenantId();
                window.location.href = '/';
                return;
            }
        }
        
        return response;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Example usage in your dashboard:
// Replace your existing fetch calls with tenantFetch

// Before:
// fetch('/api/dashboard/stats')

// After:
// tenantFetch('/api/dashboard/stats')

// Check tenant ID when dashboard loads
document.addEventListener('DOMContentLoaded', function() {
    const tenantId = TenantManager.checkTenantId();
    if (!tenantId) return; // Will redirect

    // Add logout/change tenant functionality
    addTenantControls();
    
    // Your existing dashboard initialization code here
    loadDashboardData();
});

function addTenantControls() {
    // Add a small tenant indicator/logout button to your dashboard
    const tenantId = TenantManager.getTenantId();
    const shortTenantId = tenantId.substring(0, 8) + '...';
    
    // You can add this to your dashboard header
    const tenantInfo = document.createElement('div');
    tenantInfo.className = 'tenant-info';
    tenantInfo.innerHTML = `
        <div class="flex items-center space-x-2 text-sm text-gray-600">
            <span>School: ${shortTenantId}</span>
            <button onclick="changeTenant()" class="text-indigo-600 hover:text-indigo-800">
                Change
            </button>
        </div>
    `;
    
    // Insert into your header (adjust selector based on your HTML structure)
    const header = document.querySelector('header') || document.querySelector('.header');
    if (header) {
        header.appendChild(tenantInfo);
    }
}

function changeTenant() {
    TenantManager.clearTenantId();
    window.location.href = '/';
}

// Example: Load dashboard data using the new tenantFetch
async function loadDashboardData() {
    try {
        // Load stats
        const statsResponse = await tenantFetch('/api/dashboard/stats');
        if (statsResponse && statsResponse.ok) {
            const stats = await statsResponse.json();
            updateStatsDisplay(stats);
        }

        // Load grades data
        const gradesResponse = await tenantFetch('/api/dashboard/grades');
        if (gradesResponse && gradesResponse.ok) {
            const grades = await gradesResponse.json();
            updateGradesDisplay(grades);
        }
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

// Placeholder functions - replace with your actual implementation
function updateStatsDisplay(stats) {
    console.log('Stats loaded:', stats);
    // Your stats display logic here
}

function updateGradesDisplay(grades) {
    console.log('Grades loaded:', grades);
    // Your grades display logic here
}
