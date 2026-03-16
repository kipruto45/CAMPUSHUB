#!/usr/bin/env python3
"""
Standalone script to seed all faculties, departments, and courses to the Render database.
Run with: python3 seed_courses_direct.py
"""

import psycopg2
import uuid

# Render PostgreSQL connection string
DATABASE_URL = "postgresql://campus_db_ztct_user:CN7ifpu0z9JLe461pLxPacnpV9yirSl3@dpg-d6rqio1aae7s73cu5v0g-a.oregon-postgres.render.com:5432/campus_db_ztct?sslmode=require"

def seed_courses():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Connected to database successfully!")
    
    # Insert faculties (excluding id - let PostgreSQL handle it or check existing)
    faculties = [
        ('FCIT', 'Faculty of Computing & Information Technology', 'Faculty of Computing and Information Technology'),
        ('FBE', 'Faculty of Business & Economics', 'Faculty of Business and Economics'),
        ('FCCD', 'Faculty of Communication & Creative Digital Media', 'Faculty of Communication and Creative Digital Media'),
        ('FAS', 'Faculty of Applied Sciences', 'Faculty of Applied Sciences'),
        ('FELS', 'Faculty of Environmental & Life Sciences', 'Faculty of Environmental and Life Sciences'),
        ('FAMC', 'Faculty of Arts, Media & Communication', 'Faculty of Arts, Media and Communication'),
    ]
    
    # Insert or get faculties
    faculty_ids = {}
    for code, name, desc in faculties:
        # Check if exists first
        cur.execute("SELECT id FROM faculties_faculty WHERE code = %s", (code,))
        row = cur.fetchone()
        if row:
            faculty_ids[code] = row[0]
            print(f"Faculty exists: {code} - {name} (ID: {row[0]})")
        else:
            cur.execute("""
                INSERT INTO faculties_faculty (id, code, name, description, slug, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, true, NOW(), NOW())
                RETURNING id
            """, (str(uuid.uuid4()), code, name, desc, code.lower()))
            row = cur.fetchone()
            faculty_ids[code] = row[0]
            print(f"Faculty created: {code} - {name} (ID: {row[0]})")
    
    # Insert departments
    departments = [
        # FCIT
        ('DCS', 'Department of Computer Science', 'FCIT'),
        ('DIT', 'Department of Information Technology', 'FCIT'),
        ('DDSA', 'Department of Data Science & Analytics', 'FCIT'),
        ('DCN', 'Department of Computer Networks', 'FCIT'),
        # FBE
        ('DAF', 'Department of Accounting & Finance', 'FBE'),
        ('DBAM', 'Department of Business Administration & Management', 'FBE'),
        ('DHRP', 'Department of Human Resource Management', 'FBE'),
        ('DECO', 'Department of Economics', 'FBE'),
        ('DEI', 'Department of Economics & International Relations', 'FBE'),
        # FCCD
        ('DCB', 'Department of Commerce', 'FCCD'),
        ('DRCD', 'Department of Recreation & Digital Media', 'FCCD'),
        # FAS
        ('DASM', 'Department of Arts in Social Sciences', 'FAS'),
        ('DPBS', 'Department of Pure & Biological Sciences', 'FAS'),
        # FELS
        ('DES', 'Department of Environmental Science', 'FELS'),
        # FAMC
        ('DCMT', 'Department of Community Media & Technology', 'FAMC'),
        ('DLGS', 'Department of Library & Information Science', 'FAMC'),
    ]
    
    department_ids = {}
    for code, name, faculty_code in departments:
        faculty_id = faculty_ids[faculty_code]
        # Check if exists
        cur.execute("SELECT id FROM faculties_department WHERE faculty_id = %s AND code = %s", (faculty_id, code))
        row = cur.fetchone()
        if row:
            department_ids[code] = row[0]
            print(f"Department exists: {code} - {name} (ID: {row[0]})")
        else:
            cur.execute("""
                INSERT INTO faculties_department (id, faculty_id, code, name, description, slug, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, true, NOW(), NOW())
                RETURNING id
            """, (str(uuid.uuid4()), faculty_id, code, name, name, f"{faculty_code.lower()}-{code.lower()}"))
            row = cur.fetchone()
            department_ids[code] = row[0]
            print(f"Department created: {code} - {name} (ID: {row[0]})")
    
    # Insert courses
    courses = [
        # DCS
        ('BCS', 'Bachelor of Computer Science', 4, 'DCS'),
        # DIT
        ('BIT', 'Bachelor of Information Technology', 4, 'DIT'),
        ('BBIT', 'Bachelor of Business Information Technology', 4, 'DIT'),
        ('BSIT', 'Bachelor of Science in Information Technology', 4, 'DIT'),
        ('BMIT', 'Bachelor of Management of Information Technology', 4, 'DIT'),
        # DDSA
        ('BDAT', 'Bachelor of Data Science and Analytics', 4, 'DDSA'),
        # DCN
        ('BNCS', 'Bachelor of Networks and Computer Security', 4, 'DCN'),
        # DAF
        ('BBFI', 'Bachelor of Banking and Finance', 4, 'DAF'),
        ('BSCFIN', 'Bachelor of Science in Finance', 4, 'DAF'),
        ('BSACC', 'Bachelor of Science in Accounting', 4, 'DAF'),
        # DBAM
        ('BBM', 'Bachelor of Business Management', 4, 'DBAM'),
        ('BABM', 'Bachelor of Arts in Business Management', 4, 'DBAM'),
        ('BAGE', 'Bachelor of Agribusiness', 4, 'DBAM'),
        ('BTM', 'Bachelor of Tourism Management', 4, 'DBAM'),
        ('BBEST', 'Bachelor of Business and Enterprise Management', 4, 'DBAM'),
        ('BPSM', 'Bachelor of Purchasing and Supply Management', 4, 'DBAM'),
        # DHRP
        ('BHRM', 'Bachelor of Human Resource Management', 4, 'DHRP'),
        # DECO
        ('BECO', 'Bachelor of Economics', 4, 'DECO'),
        # DEI
        ('BENT', 'Bachelor of Economics and International Trade', 4, 'DEI'),
        ('BEEP', 'Bachelor of Economics and Economic Policy', 4, 'DEI'),
        # DCB
        ('BCOB', 'Bachelor of Commerce', 4, 'DCB'),
        ('BCOM', 'Bachelor of Commerce (Online)', 4, 'DCB'),
        # DRCD
        ('BDRM', 'Bachelor of Digital Recreation and Media', 4, 'DRCD'),
        ('BDVS', 'Bachelor of Digital Video Production', 4, 'DRCD'),
        # DASM
        ('BASD', 'Bachelor of Arts in Social Development', 4, 'DASM'),
        ('BSAS', 'Bachelor of Science in Applied Statistics', 4, 'DASM'),
        ('BSCAS', 'Bachelor of Science in Actuarial Science', 4, 'DASM'),
        # DPBS
        ('BBIO', 'Bachelor of Biology', 4, 'DPBS'),
        ('BCHM', 'Bachelor of Chemistry', 4, 'DPBS'),
        # DES
        ('BSEN', 'Bachelor of Science in Environmental Science', 4, 'DES'),
        ('BELSI', 'Bachelor of Environmental Leadership and Sustainability', 4, 'DES'),
        ('BSF', 'Bachelor of Science in Forestry', 4, 'DES'),
        # DCMT
        ('BPRA', 'Bachelor of Public Relations and Advertising', 4, 'DCMT'),
        ('BCCD', 'Bachelor of Creative and Cultural Development', 4, 'DCMT'),
        ('BCD', 'Bachelor of Communication and Development', 4, 'DCMT'),
        # DLGS
        ('BLIS', 'Bachelor of Library and Information Science', 4, 'DLGS'),
    ]
    
    # Map department codes to faculty codes for slug generation
    dept_to_faculty = {
        'DCS': 'FCIT', 'DIT': 'FCIT', 'DDSA': 'FCIT', 'DCN': 'FCIT',
        'DAF': 'FBE', 'DBAM': 'FBE', 'DHRP': 'FBE', 'DECO': 'FBE', 'DEI': 'FBE',
        'DCB': 'FCCD', 'DRCD': 'FCCD',
        'DASM': 'FAS', 'DPBS': 'FAS',
        'DES': 'FELS',
        'DCMT': 'FAMC', 'DLGS': 'FAMC',
    }
    
    courses_created = 0
    for code, name, duration, dept_code in courses:
        dept_id = department_ids[dept_code]
        # Get faculty code prefix for slug (first 4 chars of faculty)
        faculty_code = dept_to_faculty.get(dept_code, 'FCIT')[:4]
        
        # Check if exists
        cur.execute("SELECT id FROM courses_course WHERE department_id = %s AND code = %s", (dept_id, code))
        row = cur.fetchone()
        if row:
            print(f"Course exists: {code} - {name}")
        else:
            cur.execute("""
                INSERT INTO courses_course (id, department_id, name, code, description, slug, duration_years, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, '', %s, %s, true, NOW(), NOW())
                RETURNING id
            """, (str(uuid.uuid4()), dept_id, name, code, f"{faculty_code.lower()}-{code.lower()}", duration))
            row = cur.fetchone()
            courses_created += 1
            print(f"Course created: {code} - {name} (ID: {row[0]})")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n=== Summary ===")
    print(f"Faculties: {len(faculties)}")
    print(f"Departments: {len(departments)}")
    print(f"Courses created: {courses_created}")

if __name__ == "__main__":
    seed_courses()
