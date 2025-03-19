CREATE TABLE leaderboard (
    id SERIAL PRIMARY KEY,
    course_id TEXT NOT NULL,
    username TEXT NOT NULL,
    score INT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_id, username)  -- Ensure one score per user per course
);
