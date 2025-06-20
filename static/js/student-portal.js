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
    }

    bindEvents() {
        this.searchBtn.addEventListener('click', () => this.searchGrades());
        this.clearBtn.addEventListener('click', () => this.clearResults());
        
        this.emailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.searchGrades();
            }
        });

        this.emailInput.addEventListener('input', () => {
            if (this.emailInput.value.trim() === '') {
                this.clearResults();
            }
        });
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

        if (!this.isValidEmail(email)) {
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
        const gradeClass = this.getGradeClass(overallPercentage);
        const gradeLetter = this.getGradeLetter(overallPercentage);
        
        const gradesTableHtml = student.grades && student.grades.length > 0 
            ? this.generateGradesTable(student.grades)
            : '<p class="no-data">No assignments found.</p>';

        // Update search stats
        this.searchStats.textContent = `Found ${student.total_assignments || 0} assignments for ${student.first_name} ${student.last_name}`;
        this.searchStats.style.display = 'block';

        this.resultsSection.innerHTML = `
            <div class="student-header">
                <div class="student-name">${this.escapeHtml(student.first_name)} ${this.escapeHtml(student.last_name)}</div>
                <div class="student-email">${this.escapeHtml(student.email)}</div>
                
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
            const percentage = grade.max_points > 0 ? (grade.score / grade.max_points) * 100 : 0;
            const gradeClass = this.getGradeClass(percentage);
            const date = grade.date ? new Date(grade.date).toLocaleDateString() : 'No date';
            
            return `
                <tr>
                    <td>
                        <div class="assignment-name">${this.escapeHtml(grade.assignment)}</div>
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

    getGradeClass(percentage) {
        if (percentage >= 90) return 'grade-a';
        if (percentage >= 80) return 'grade-b';
        if (percentage >= 70) return 'grade-c';
        if (percentage >= 60) return 'grade-d';
        return 'grade-f';
    }

    getGradeLetter(percentage) {
        if (percentage >= 90) return 'A';
        if (percentage >= 80) return 'B';
        if (percentage >= 70) return 'C';
        if (percentage >= 60) return 'D';
        return 'F';
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
        this.resultsSection.innerHTML = `
            <div class="error">
                <strong>Error:</strong> ${this.escapeHtml(message)}
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }

    showNotFound(email) {
        this.resultsSection.innerHTML = `
            <div class="not-found">
                <h3>Student Not Found</h3>
                <p>No student found with email address: <strong>${this.escapeHtml(email)}</strong></p>
                <p>Please check your email address and try again.</p>
            </div>
        `;
        this.resultsSection.style.display = 'block';
    }

    isValidEmail(email) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(email);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the student portal when the page loads
document.addEventListener('DOMContentLoaded', () => {
    const portal = new StudentGradePortal();
    const params = new URLSearchParams(window.location.search);
    const emailFromURL = params.get('email');
    if (emailFromURL) {
        portal.emailInput.value = decodeURIComponent(emailFromURL);
        portal.searchGrades();
    }
});
