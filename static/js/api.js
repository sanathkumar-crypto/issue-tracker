// API Client for Flask Backend

const API_BASE = '/api';

class APIClient {
    constructor() {
        this.token = null;
        this.currentUser = null;
    }

    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        const config = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        if (this.token) {
            config.headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Auth methods
    async login(email) {
        const data = await this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email })
        });
        this.currentUser = data;
        return data;
    }
    
    async getCurrentUser() {
        return this.request('/auth/current');
    }

    async logout() {
        await this.request('/auth/logout', { method: 'POST' });
        this.token = null;
        this.currentUser = null;
    }

    // Issues methods
    async getIssues(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/issues?${queryString}`);
    }

    async getIssue(issueId) {
        return this.request(`/issues/${issueId}`);
    }

    async createIssue(issueData) {
        return this.request('/issues', {
            method: 'POST',
            body: JSON.stringify(issueData)
        });
    }

    async updateIssue(issueId, updateData) {
        return this.request(`/issues/${issueId}`, {
            method: 'PUT',
            body: JSON.stringify(updateData)
        });
    }

    async deleteIssue(issueId) {
        return this.request(`/issues/${issueId}`, {
            method: 'DELETE'
        });
    }

    // Dashboard methods
    async getDashboardStats() {
        return this.request('/dashboard/stats');
    }

    // Settings methods
    async getHospitals() {
        const hospitals = await this.request('/settings/hospitals');
        return Array.isArray(hospitals) ? hospitals : [];
    }

    async getTeamMembers() {
        const team = await this.request('/settings/team');
        return Array.isArray(team) ? team : [];
    }
}

// Export singleton instance
const apiClient = new APIClient();
export { apiClient };

