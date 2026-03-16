-- SQL commands to seed academic units for CampusHub
-- Run this directly on the database

-- Create Faculty (if not exists)
INSERT OR IGNORE INTO faculties_faculty (name, code, description, slug, is_active, created_at, updated_at)
VALUES ('School of Computing', 'SOC', 'School of Computing and Information Technology', 'soc', 1, datetime('now'), datetime('now'));

-- Get faculty ID
-- Create Department (if not exists)  
INSERT OR IGNORE INTO faculties_department (name, code, description, slug, is_active, faculty_id, created_at, updated_at)
SELECT 'Computer Science', 'CS', 'Department of Computer Science', 'soc-cs', 1, id, datetime('now'), datetime('now')
FROM faculties_faculty WHERE code = 'SOC';

-- Create Courses
INSERT OR IGNORE INTO courses_course (name, code, description, slug, duration_years, is_active, department_id, created_at, updated_at)
SELECT 'Bachelor of Science in Computer Science', 'BCSC', '', 'bcsoc-bcsc', 4, 1, id, datetime('now'), datetime('now')
FROM faculties_department WHERE code = 'CS';

INSERT OR IGNORE INTO courses_course (name, code, description, slug, duration_years, is_active, department_id, created_at, updated_at)
SELECT 'Bachelor of Science in Information Technology', 'BCIT', '', 'soc-bcit', 4, 1, id, datetime('now'), datetime('now')
FROM faculties_department WHERE code = 'CS';

INSERT OR IGNORE INTO courses_course (name, code, description, slug, duration_years, is_active, department_id, created_at, updated_at)
SELECT 'Bachelor of Statistics', 'BSTA', '', 'soc-bsta', 4, 1, id, datetime('now'), datetime('now')
FROM faculties_department WHERE code = 'CS';

INSERT OR IGNORE INTO courses_course (name, code, description, slug, duration_years, is_active, department_id, created_at, updated_at)
SELECT 'Bachelor of Data Science', 'BDSC', '', 'soc-bdsc', 4, 1, id, datetime('now'), datetime('now')
FROM faculties_department WHERE code = 'CS';

INSERT OR IGNORE INTO courses_course (name, code, description, slug, duration_years, is_active, department_id, created_at, updated_at)
SELECT 'Bachelor of Computer Technology', 'BCTT', '', 'soc-bctt', 4, 1, id, datetime('now'), datetime('now')
FROM faculties_department WHERE code = 'CS';

-- Create Units
INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Scientific Computing', 'BCSC 2207', '', 'bcsoc-bcsc-2207-s2', '2', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BCSC';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Software Engineering', 'BCIT 2214', '', 'soc-bcit-2214-s2', '2', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BCIT';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Probability and Statistics III', 'BSTA 2206', '', 'soc-bsta-2206-s2', '2', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BSTA';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Linear Models II', 'BSTA 2134', '', 'soc-bsta-2134-s1', '1', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BSTA';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Data Communication', 'BDSC 2203', '', 'soc-bdsc-2203-s1', '1', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BDSC';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Internet Application Programming', 'BCTT 2218', '', 'soc-bctt-2218-s2', '2', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BCTT';

INSERT OR IGNORE INTO courses_unit (name, code, description, slug, semester, year_of_study, is_active, course_id, created_at, updated_at)
SELECT 'Data Preparation', 'BDSC 2203', '', 'soc-bdsc-2203-s2', '2', 2, 1, id, datetime('now'), datetime('now')
FROM courses_course WHERE code = 'BDSC';
