// API Utilities for Course Service Integration
// Add this to a separate file like 'js/api-utils.js' or include in your HTML

class CourseAPI {
    constructor(baseURL = 'http://localhost:8001/api/course') {
        this.baseURL = baseURL;
    }

    // Generic fetch wrapper with error handling
    async fetchWithErrorHandling(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Network error' }));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Course endpoints
    async getCourses(params = {}) {
        const queryString = new URLSearchParams({
            skip: params.skip || 0,
            limit: params.limit || 100,
            active_only: params.activeOnly !== false,
            ...(params.difficulty && { difficulty: params.difficulty })
        }).toString();

        return this.fetchWithErrorHandling(`${this.baseURL}/courses/?${queryString}`);
    }

    async getCourse(courseId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/courses/${courseId}`);
    }

    async createCourse(courseData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/courses/`, {
            method: 'POST',
            body: JSON.stringify(courseData)
        });
    }

    async updateCourse(courseId, courseData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/courses/${courseId}`, {
            method: 'PUT',
            body: JSON.stringify(courseData)
        });
    }

    async deleteCourse(courseId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/courses/${courseId}`, {
            method: 'DELETE'
        });
    }

    // Topic endpoints
    async getTopicWithLessons(topicId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/topics/${topicId}`);
    }

    async createTopic(topicData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/topics/`, {
            method: 'POST',
            body: JSON.stringify(topicData)
        });
    }

    async updateTopic(topicId, topicData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/topics/${topicId}`, {
            method: 'PUT',
            body: JSON.stringify(topicData)
        });
    }

    async deleteTopic(topicId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/topics/${topicId}`, {
            method: 'DELETE'
        });
    }

    // Lesson endpoints
    async getLesson(lessonId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/${lessonId}`);
    }

    async createLesson(lessonData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/`, {
            method: 'POST',
            body: JSON.stringify(lessonData)
        });
    }

    async updateLesson(lessonId, lessonData) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/${lessonId}`, {
            method: 'PUT',
            body: JSON.stringify(lessonData)
        });
    }

    async deleteLesson(lessonId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/${lessonId}`, {
            method: 'DELETE'
        });
    }

    async publishLesson(lessonId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/${lessonId}/publish`, {
            method: 'PUT'
        });
    }

    async unpublishLesson(lessonId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/${lessonId}/unpublish`, {
            method: 'PUT'
        });
    }

    // Utility endpoints
    async getCourseMetadata(courseId) {
        return this.fetchWithErrorHandling(`${this.baseURL}/courses/${courseId}/metadata`);
    }

    async getLessonsByDifficulty(difficulty, limit = 50) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/by-difficulty/${difficulty}?limit=${limit}`);
    }

    async searchContent(query, limit = 20) {
        const params = new URLSearchParams({ q: query, limit });
        return this.fetchWithErrorHandling(`${this.baseURL}/search?${params}`);
    }

    async healthCheck() {
        return this.fetchWithErrorHandling(`${this.baseURL}/health`);
    }

    // Batch operations
    async batchCreateLessons(lessons) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/batch`, {
            method: 'POST',
            body: JSON.stringify({ lessons })
        });
    }

    async batchUpdateLessons(updates) {
        return this.fetchWithErrorHandling(`${this.baseURL}/lessons/batch`, {
            method: 'PUT',
            body: JSON.stringify({ updates })
        });
    }
}

// Content mapping utilities
class ContentMapper {
    static mapLessonToArticle(lesson) {
        return {
            id: lesson.id,
            title: lesson.title,
            subtitle: `${lesson.lesson_type} • ${lesson.difficulty}`,
            content: lesson.content,
            learning_objectives: lesson.learning_objectives || [],
            key_concepts: lesson.key_concepts || [],
            estimated_duration_minutes: lesson.estimated_duration_minutes,
            xp_reward: lesson.xp_reward,
            difficulty: lesson.difficulty,
            lesson_type: lesson.lesson_type,
            status: lesson.status,
            prerequisites: lesson.prerequisites || [],
            tags: lesson.tags || [],
            created_at: lesson.created_at,
            updated_at: lesson.updated_at
        };
    }

    static mapTopicToArticle(topic) {
        return {
            id: topic.id,
            title: topic.title,
            subtitle: topic.description,
            content: this.generateTopicContent(topic),
            learning_objectives: topic.learning_objectives || [],
            key_concepts: topic.key_concepts || [],
            estimated_duration_minutes: topic.estimated_duration_minutes,
            difficulty: topic.difficulty,
            lessons: topic.lessons || [],
            course_id: topic.course_id,
            order_index: topic.order_index,
            created_at: topic.created_at,
            updated_at: topic.updated_at
        };
    }

    static mapCourseToArticle(course) {
        return {
            id: course.id,
            title: course.title,
            subtitle: course.description,
            content: this.generateCourseContent(course),
            learning_objectives: course.learning_objectives || [],
            key_concepts: course.key_concepts || [],
            estimated_duration_minutes: course.estimated_duration_hours * 60,
            difficulty: course.difficulty,
            topics: course.topics || [],
            is_active: course.is_active,
            instructor: course.instructor,
            category: course.category,
            created_at: course.created_at,
            updated_at: course.updated_at
        };
    }

    static generateTopicContent(topic) {
        const lessonCount = topic.lessons ? topic.lessons.length : 0;
        return `
            <h2>Topic Overview</h2>
            <p>${topic.description || 'This topic covers important concepts in the subject area.'}</p>

            <h2>What You'll Learn</h2>
            <p>This topic contains ${lessonCount} lesson${lessonCount !== 1 ? 's' : ''} designed to help you master the key concepts and skills.</p>

            ${topic.learning_objectives && topic.learning_objectives.length > 0 ? `
                <h2>Learning Objectives</h2>
                <ul>
                    ${topic.learning_objectives.map(obj => `<li>${obj}</li>`).join('')}
                </ul>
            ` : ''}

            <h2>Prerequisites</h2>
            <p>Make sure you have completed the previous topics before starting this one.</p>
        `;
    }

    static generateCourseContent(course) {
        const topicCount = course.topics ? course.topics.length : 0;
        return `
            <h2>Course Overview</h2>
            <p>${course.description || 'This comprehensive course will take you through all the essential concepts.'}</p>

            <h2>Course Structure</h2>
            <p>This course is organized into ${topicCount} topic${topicCount !== 1 ? 's' : ''}, each containing multiple lessons with hands-on examples and exercises.</p>

            ${course.instructor ? `
                <h2>Instructor</h2>
                <p>This course is taught by ${course.instructor}, bringing years of experience in the field.</p>
            ` : ''}

            <h2>Learning Path</h2>
            <p>Follow the structured learning path to build your knowledge step by step, from basic concepts to advanced applications.</p>

            ${course.category ? `
                <h2>Category</h2>
                <p>This course belongs to the ${course.category} category.</p>
            ` : ''}
        `;
    }

    // Convert API data to display format
    static formatLessonForDisplay(lesson) {
        return {
            ...lesson,
            duration_display: this.formatDuration(lesson.estimated_duration_minutes),
            difficulty_display: this.formatDifficulty(lesson.difficulty),
            status_display: this.formatStatus(lesson.status),
            type_display: this.formatLessonType(lesson.lesson_type)
        };
    }

    static formatDuration(minutes) {
        if (!minutes) return 'Unknown';
        if (minutes < 60) return `${minutes} min`;
        const hours = Math.floor(minutes / 60);
        const remainingMins = minutes % 60;
        return `${hours}h ${remainingMins}min`;
    }

    static formatDifficulty(difficulty) {
        const difficultyMap = {
            'BEGINNER': 'Beginner',
            'INTERMEDIATE': 'Intermediate',
            'ADVANCED': 'Advanced',
            'EXPERT': 'Expert'
        };
        return difficultyMap[difficulty] || difficulty;
    }

    static formatStatus(status) {
        const statusMap = {
            'DRAFT': 'Draft',
            'PUBLISHED': 'Published',
            'ARCHIVED': 'Archived',
            'REVIEW': 'Under Review'
        };
        return statusMap[status] || status;
    }

    static formatLessonType(type) {
        const typeMap = {
            'READING': 'Reading',
            'VIDEO': 'Video',
            'INTERACTIVE': 'Interactive',
            'QUIZ': 'Quiz',
            'ASSIGNMENT': 'Assignment',
            'PROJECT': 'Project'
        };
        return typeMap[type] || type;
    }
}

// URL parameter utilities
class URLUtils {
    static getParams() {
        const urlParams = new URLSearchParams(window.location.search);
        return {
            lessonId: urlParams.get('lesson'),
            topicId: urlParams.get('topic'),
            courseId: urlParams.get('course'),
            sectionId: urlParams.get('section'), // for backward compatibility
            page: parseInt(urlParams.get('page')) || 1,
            limit: parseInt(urlParams.get('limit')) || 20,
            difficulty: urlParams.get('difficulty'),
            search: urlParams.get('search'),
            filter: urlParams.get('filter')
        };
    }

    static buildArticleURL(type, id, additionalParams = {}) {
        const params = new URLSearchParams();
        params.set(type, id);

        Object.entries(additionalParams).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                params.set(key, value);
            }
        });

        return `ArticlePage.html?${params.toString()}`;
    }

    static buildLessonURL(lessonId, additionalParams = {}) {
        return this.buildArticleURL('lesson', lessonId, additionalParams);
    }

    static buildTopicURL(topicId, additionalParams = {}) {
        return this.buildArticleURL('topic', topicId, additionalParams);
    }

    static buildCourseURL(courseId, additionalParams = {}) {
        return this.buildArticleURL('course', courseId, additionalParams);
    }

    static buildSearchURL(query, filters = {}) {
        const params = new URLSearchParams();
        params.set('search', query);

        Object.entries(filters).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                params.set(key, value);
            }
        });

        return `SearchResults.html?${params.toString()}`;
    }

    static updateURL(newParams, replaceState = false) {
        const url = new URL(window.location);
        Object.entries(newParams).forEach(([key, value]) => {
            if (value === null || value === undefined) {
                url.searchParams.delete(key);
            } else {
                url.searchParams.set(key, value);
            }
        });

        if (replaceState) {
            window.history.replaceState({}, '', url);
        } else {
            window.history.pushState({}, '', url);
        }
    }
}

// Error handling utilities
class ErrorHandler {
    static handleAPIError(error, fallbackData = null) {
        console.error('API Error:', error);

        // Categorize errors for better user experience
        if (error.message.includes('404')) {
            return {
                error: 'Content not found. Please check the URL or try again later.',
                fallback: fallbackData,
                type: 'NOT_FOUND',
                shouldRetry: false
            };
        } else if (error.message.includes('500')) {
            return {
                error: 'Server error. Please try again later.',
                fallback: fallbackData,
                type: 'SERVER_ERROR',
                shouldRetry: true
            };
        } else if (error.message.includes('Network') || error.name === 'TypeError') {
            return {
                error: 'Network error. Please check your connection.',
                fallback: fallbackData,
                type: 'NETWORK_ERROR',
                shouldRetry: true
            };
        } else if (error.message.includes('timeout') || error.name === 'AbortError') {
            return {
                error: 'Request timed out. Please try again.',
                fallback: fallbackData,
                type: 'TIMEOUT',
                shouldRetry: true
            };
        } else if (error.message.includes('401') || error.message.includes('403')) {
            return {
                error: 'Access denied. Please check your permissions.',
                fallback: fallbackData,
                type: 'AUTH_ERROR',
                shouldRetry: false
            };
        } else {
            return {
                error: 'An unexpected error occurred. Please try again.',
                fallback: fallbackData,
                type: 'UNKNOWN',
                shouldRetry: true
            };
        }
    }

    static createFallbackContent(type = 'lesson', id = 1) {
        const fallbacks = {
            lesson: {
                id: id,
                title: "Sample Lesson",
                subtitle: "Introduction to Neural Networks",
                content: `
                    <h2>What is a Neural Network?</h2>
                    <p>A neural network is a computational model inspired by biological neural networks that constitute animal brains. Such networks "learn" to perform tasks by considering examples, generally without being programmed with task-specific rules.</p>

                    <h2>Key Components</h2>
                    <p>Neural networks consist of interconnected nodes or neurons that process information using a connectionist approach to computation. The connections have numeric weights that can be tuned based on experience, making neural networks adaptive to inputs and capable of learning.</p>

                    <h2>Applications</h2>
                    <p>Neural networks are used in various applications including image recognition, natural language processing, medical diagnosis, and autonomous vehicles.</p>
                `,
                learning_objectives: [
                    "Understand basic neural network concepts",
                    "Learn about network architecture",
                    "Explore real-world applications"
                ],
                key_concepts: [
                    "Neural Network",
                    "Artificial Neuron",
                    "Deep Learning",
                    "Machine Learning"
                ],
                estimated_duration_minutes: 15,
                xp_reward: 100,
                difficulty: "BEGINNER",
                lesson_type: "READING",
                status: "PUBLISHED"
            },
            topic: {
                id: id,
                title: "Sample Topic",
                subtitle: "Neural Network Fundamentals",
                content: `
                    <h2>Topic Overview</h2>
                    <p>This topic covers the fundamental concepts of neural networks, providing a solid foundation for understanding artificial intelligence and machine learning.</p>

                    <h2>Learning Path</h2>
                    <p>You'll progress through carefully structured lessons that build upon each other, ensuring a comprehensive understanding of the subject matter.</p>
                `,
                learning_objectives: [
                    "Master neural network fundamentals",
                    "Apply concepts to real problems"
                ],
                key_concepts: [
                    "Neural Networks",
                    "Deep Learning",
                    "AI Fundamentals"
                ],
                estimated_duration_minutes: 60,
                difficulty: "BEGINNER"
            },
            course: {
                id: id,
                title: "Sample Course",
                subtitle: "Introduction to Machine Learning",
                content: `
                    <h2>Course Overview</h2>
                    <p>This comprehensive course introduces you to the exciting world of machine learning and artificial intelligence.</p>

                    <h2>What You'll Achieve</h2>
                    <p>By the end of this course, you'll have a solid understanding of ML concepts and be able to apply them to solve real-world problems.</p>
                `,
                learning_objectives: [
                    "Understand machine learning principles",
                    "Build practical ML applications",
                    "Master key algorithms and techniques"
                ],
                key_concepts: [
                    "Machine Learning",
                    "Artificial Intelligence",
                    "Data Science",
                    "Algorithm Design"
                ],
                estimated_duration_minutes: 480, // 8 hours
                difficulty: "BEGINNER",
                instructor: "AI Learning Team",
                category: "Technology"
            }
        };

        return fallbacks[type] || fallbacks.lesson;
    }

    static logError(error, context = {}) {
        const errorLog = {
            timestamp: new Date().toISOString(),
            error: {
                message: error.message,
                stack: error.stack,
                name: error.name
            },
            context,
            userAgent: navigator.userAgent,
            url: window.location.href
        };

        // In production, you might want to send this to a logging service
        console.error('Detailed Error Log:', errorLog);

        // Store recent errors in localStorage for debugging
        try {
            const recentErrors = JSON.parse(localStorage.getItem('recentErrors') || '[]');
            recentErrors.push(errorLog);

            // Keep only the last 10 errors
            if (recentErrors.length > 10) {
                recentErrors.splice(0, recentErrors.length - 10);
            }

            localStorage.setItem('recentErrors', JSON.stringify(recentErrors));
        } catch (e) {
            console.warn('Could not save error to localStorage:', e);
        }
    }
}

// Cache utilities for better performance
class CacheManager {
    constructor(maxAge = 5 * 60 * 1000) { // 5 minutes default
        this.cache = new Map();
        this.maxAge = maxAge;
    }

    set(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }

    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;

        if (Date.now() - item.timestamp > this.maxAge) {
            this.cache.delete(key);
            return null;
        }

        return item.data;
    }

    clear() {
        this.cache.clear();
    }

    has(key) {
        const item = this.cache.get(key);
        if (!item) return false;

        if (Date.now() - item.timestamp > this.maxAge) {
            this.cache.delete(key);
            return false;
        }

        return true;
    }
}

// Enhanced API class with caching and retry logic
class EnhancedCourseAPI extends CourseAPI {
    constructor(baseURL = 'http://localhost:8001/api/course', options = {}) {
        super(baseURL);
        this.cache = new CacheManager(options.cacheMaxAge);
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.timeout = options.timeout || 10000;
    }

    async fetchWithRetry(url, options = {}, attempt = 1) {
        const cacheKey = `${url}-${JSON.stringify(options)}`;

        // Check cache for GET requests
        if (!options.method || options.method === 'GET') {
            const cached = this.cache.get(cacheKey);
            if (cached) {
                console.log('Returning cached data for:', url);
                return cached;
            }
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);

            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    ...options.headers
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: `HTTP ${response.status}: ${response.statusText}`
                }));
                throw new Error(errorData.detail || `Request failed with status ${response.status}`);
            }

            const data = await response.json();

            // Cache successful GET requests
            if (!options.method || options.method === 'GET') {
                this.cache.set(cacheKey, data);
            }

            return data;
        } catch (error) {
            ErrorHandler.logError(error, { url, attempt, options });

            if (attempt < this.maxRetries && error.name !== 'AbortError') {
                console.log(`Retrying request (${attempt}/${this.maxRetries}) in ${this.retryDelay}ms...`);
                await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                return this.fetchWithRetry(url, options, attempt + 1);
            }

            throw error;
        }
    }

    // Override parent methods to use retry logic
    async fetchWithErrorHandling(url, options = {}) {
        return this.fetchWithRetry(url, options);
    }

    // Additional utility methods
    async preloadContent(contentIds) {
        const promises = contentIds.map(async (id) => {
            try {
                if (id.type === 'lesson') {
                    await this.getLesson(id.id);
                } else if (id.type === 'topic') {
                    await this.getTopicWithLessons(id.id);
                } else if (id.type === 'course') {
                    await this.getCourse(id.id);
                }
            } catch (error) {
                console.warn(`Failed to preload ${id.type} ${id.id}:`, error);
            }
        });

        await Promise.allSettled(promises);
    }

    clearCache() {
        this.cache.clear();
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CourseAPI,
        EnhancedCourseAPI,
        ContentMapper,
        URLUtils,
        ErrorHandler,
        CacheManager
    };
}

// Global initialization for browser environment
if (typeof window !== 'undefined') {
    window.CourseAPI = CourseAPI;
    window.EnhancedCourseAPI = EnhancedCourseAPI;
    window.ContentMapper = ContentMapper;
    window.URLUtils = URLUtils;
    window.ErrorHandler = ErrorHandler;
    window.CacheManager = CacheManager;
}
