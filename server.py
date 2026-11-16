import http.server
import socketserver
import json
import sqlite3
import os
import urllib.parse
from datetime import datetime

PORT = 8080
DB_FILE = os.path.join(os.path.dirname(__file__), 'database.db')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Jobs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            location TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            min_experience INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Candidates table
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            headline TEXT,
            skills TEXT,
            experience_years INTEGER DEFAULT 0,
            location TEXT,
            stage TEXT DEFAULT 'Sourced',
            match_score INTEGER DEFAULT 0,
            match_breakdown TEXT,
            sequence_status TEXT DEFAULT 'Not Started',
            sequence_step INTEGER DEFAULT 0,
            last_activity TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        )
    ''')
    # Outreach activity logs
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Seed default sample data if empty
    c.execute("SELECT COUNT(*) FROM jobs")
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO jobs (title, department, location, required_skills, min_experience)
            VALUES 
            ('Senior Product Manager', 'Product', 'Remote (Global)', 'Product Strategy, Roadmap Planning, B2B SaaS, User Stories, Agile, Data Analytics', 4),
            ('Full Stack Engineer (React/Python)', 'Engineering', 'Remote (US/India)', 'React, Python, TypeScript, REST APIs, PostgreSQL, Docker', 3),
            ('Executive Search Recruiter', 'Talent Acquisition', 'London / Remote', 'Executive Search, Sourcing, Headhunting, Boolean Search, Client Management', 2)
        ''')
        conn.commit()

        # Seed initial candidates
        c.execute('''
            INSERT INTO candidates (job_id, name, email, headline, skills, experience_years, location, stage, match_score, match_breakdown, sequence_status, sequence_step, last_activity)
            VALUES 
            (1, 'Aarav Mehta', 'aarav.mehta@example.com', 'Senior APM at SaaS Scale-Up | Ex-Fintech', 'Product Strategy, B2B SaaS, User Stories, Agile, Data Analytics, Figma', 5, 'Bangalore / Remote', 'Shortlisted', 94, '{"matched": ["Product Strategy", "B2B SaaS", "User Stories", "Agile", "Data Analytics"], "missing": ["Roadmap Planning"], "exp_match": true}', 'Engaged', 2, 'Candidate replied to Email Step 1'),
            (1, 'Sophia Rodriguez', 'sophia.r@techmail.io', 'Product Specialist & Growth Lead', 'Product Strategy, User Stories, Figma, Customer Research, Wireframing', 3, 'Remote (US)', 'Sourced', 68, '{"matched": ["Product Strategy", "User Stories"], "missing": ["B2B SaaS", "Roadmap Planning", "Agile", "Data Analytics"], "exp_match": false}', 'Active Sequence', 1, 'Sent: Initial Intro & Role Pitch'),
            (1, 'Marcus Chen', 'marcus.chen@innovate.co', 'Technical PM | B2B Cloud Solutions', 'B2B SaaS, Roadmap Planning, Agile, Cloud, Python, Data Analytics', 4, 'Singapore / Remote', 'Interview', 86, '{"matched": ["B2B SaaS", "Roadmap Planning", "Agile", "Data Analytics"], "missing": ["Product Strategy", "User Stories"], "exp_match": true}', 'Completed', 2, 'Scheduled Screening Call'),
            (2, 'Priya Sharma', 'priya.sharma@devhub.com', 'Senior Full Stack Developer', 'React, Python, TypeScript, PostgreSQL, Docker, AWS', 4, 'Remote (India)', 'Sourced', 95, '{"matched": ["React", "Python", "TypeScript", "PostgreSQL", "Docker"], "missing": ["REST APIs"], "exp_match": true}', 'Active Sequence', 1, 'Sent: Initial Technical Outreach')
        ''')
        conn.commit()

    conn.close()

def compute_match(job_skills_str, min_exp, cand_skills_str, cand_exp):
    req_skills = [s.strip().lower() for s in job_skills_str.split(',') if s.strip()]
    cand_skills = [s.strip().lower() for s in cand_skills_str.split(',') if s.strip()]
    
    if not req_skills:
        return 100, {"matched": cand_skills, "missing": [], "exp_match": True}
        
    matched = []
    missing = []
    for r in req_skills:
        # Match if substring exists or vice-versa
        found = False
        for c in cand_skills:
            if r in c or c in r:
                found = True
                matched.append(r.title())
                break
        if not found:
            missing.append(r.title())
            
    skill_pct = (len(matched) / len(req_skills)) * 75.0
    exp_pct = 25.0 if cand_exp >= min_exp else (cand_exp / max(min_exp, 1)) * 25.0
    total_score = min(100, int(round(skill_pct + exp_pct)))
    
    return total_score, {
        "matched": matched,
        "missing": missing,
        "exp_match": cand_exp >= min_exp
    }

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path.startswith('/api/jobs'):
            self.get_jobs()
        elif path.startswith('/api/candidates'):
            self.get_candidates(url.query)
        elif path.startswith('/api/metrics'):
            self.get_metrics()
        else:
            # Serve static files from static directory
            static_dir = os.path.join(os.path.dirname(__file__), 'static')
            file_path = path.lstrip('/')
            if not file_path or file_path == '':
                file_path = 'index.html'
            full_path = os.path.join(static_dir, file_path)
            
            if os.path.exists(full_path) and not os.path.isdir(full_path):
                self.send_response(200)
                if file_path.endswith('.html'):
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                elif file_path.endswith('.css'):
                    self.send_header('Content-Type', 'text/css')
                elif file_path.endswith('.js'):
                    self.send_header('Content-Type', 'application/javascript')
                self.end_headers()
                with open(full_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"404 Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        data = json.loads(body) if body else {}

        if path == '/api/candidates/import':
            self.import_candidate(data)
        elif path == '/api/candidates/update-stage':
            self.update_stage(data)
        elif path == '/api/candidates/trigger-sequence':
            self.trigger_sequence(data)
        elif path == '/api/candidates/check-duplicate':
            self.check_duplicate(data)
        elif path == '/api/jobs/create':
            self.create_job(data)
        else:
            self.send_response(404)
            self.end_headers()

    def get_jobs(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM jobs ORDER BY id DESC")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(rows).encode('utf-8'))

    def get_candidates(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        job_id = params.get('job_id', [None])[0]
        
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if job_id:
            c.execute("SELECT * FROM candidates WHERE job_id = ? ORDER BY match_score DESC", (job_id,))
        else:
            c.execute("SELECT * FROM candidates ORDER BY id DESC")
        rows = []
        for r in c.fetchall():
            d = dict(r)
            if d.get('match_breakdown'):
                try:
                    d['match_breakdown'] = json.loads(d['match_breakdown'])
                except:
                    pass
            rows.append(d)
        conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(rows).encode('utf-8'))

    def get_metrics(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM candidates")
        total_candidates = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM candidates WHERE sequence_status = 'Active Sequence'")
        active_sequences = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM candidates WHERE stage = 'Interview' OR sequence_status = 'Engaged'")
        engaged_count = c.fetchone()[0]
        c.execute("SELECT AVG(match_score) FROM candidates")
        avg_score = round(c.fetchone()[0] or 0, 1)
        conn.close()

        res = {
            "total_candidates": total_candidates,
            "active_sequences": active_sequences,
            "engaged_candidates": engaged_count,
            "avg_match_score": avg_score,
            "time_to_submit_days": 2.8,
            "time_saved_percent": "42%"
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(res).encode('utf-8'))

    def check_duplicate(self, data):
        email = data.get('email', '').strip().lower()
        name = data.get('name', '').strip()
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM candidates WHERE LOWER(email) = ? OR LOWER(name) = ?", (email, name.lower()))
        row = c.fetchone()
        conn.close()

        res = {"is_duplicate": False}
        if row:
            res = {
                "is_duplicate": True,
                "candidate": dict(row)
            }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(res).encode('utf-8'))

    def import_candidate(self, data):
        job_id = int(data.get('job_id', 1))
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        headline = data.get('headline', '')
        skills = data.get('skills', '')
        experience = int(data.get('experience_years', 0))
        location = data.get('location', '')
        auto_sequence = data.get('auto_sequence', True)

        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Fetch job criteria
        c.execute("SELECT required_skills, min_experience FROM jobs WHERE id = ?", (job_id,))
        job = c.fetchone()
        if job:
            score, breakdown = compute_match(job['required_skills'], job['min_experience'], skills, experience)
        else:
            score, breakdown = 70, {}

        seq_status = 'Active Sequence' if auto_sequence else 'Not Started'
        seq_step = 1 if auto_sequence else 0
        last_act = 'Sent: Automated Pitch Step 1' if auto_sequence else 'Candidate Imported'

        c.execute('''
            INSERT INTO candidates 
            (job_id, name, email, headline, skills, experience_years, location, stage, match_score, match_breakdown, sequence_status, sequence_step, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, name, email, headline, skills, experience, location, 'Sourced', score, json.dumps(breakdown), seq_status, seq_step, last_act))
        cand_id = c.lastrowid

        c.execute('''
            INSERT INTO activity_logs (candidate_id, action, details)
            VALUES (?, 'Candidate Imported', ?)
        ''', (cand_id, f"Imported with {score}% Requisition Match Score"))

        if auto_sequence:
            c.execute('''
                INSERT INTO activity_logs (candidate_id, action, details)
                VALUES (?, 'Sequence Triggered', 'Automated Multi-Touch Step 1 Email Dispatched')
            ''', (cand_id,))

        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "candidate_id": cand_id, "match_score": score}).encode('utf-8'))

    def update_stage(self, data):
        candidate_id = int(data.get('candidate_id'))
        new_stage = data.get('new_stage')

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        last_act = f"Moved to stage: {new_stage}"
        seq_status_update = ""
        if new_stage in ['Interview', 'Client Review', 'Offer']:
            seq_status_update = ", sequence_status = 'Engaged'"

        c.execute(f'''
            UPDATE candidates 
            SET stage = ?, last_activity = ? {seq_status_update}
            WHERE id = ?
        ''', (new_stage, last_act, candidate_id))

        c.execute('''
            INSERT INTO activity_logs (candidate_id, action, details)
            VALUES (?, 'Stage Change', ?)
        ''', (candidate_id, f"Candidate advanced to {new_stage}"))

        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode('utf-8'))

    def trigger_sequence(self, data):
        candidate_id = int(data.get('candidate_id'))
        action = data.get('action') # 'next_step' or 'pause' or 'reply'

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if action == 'next_step':
            c.execute('''
                UPDATE candidates 
                SET sequence_step = sequence_step + 1,
                    last_activity = 'Sent Follow-up Step 2 Email',
                    sequence_status = 'Step 2 Dispatched'
                WHERE id = ?
            ''', (candidate_id,))
            c.execute('''
                INSERT INTO activity_logs (candidate_id, action, details)
                VALUES (?, 'Follow-up Email', 'Automated Step 2 Follow-Up sent after 3-day inactivity')
            ''', (candidate_id,))
        elif action == 'reply':
            c.execute('''
                UPDATE candidates 
                SET sequence_status = 'Engaged',
                    stage = 'Shortlisted',
                    last_activity = 'Candidate replied with interest'
                WHERE id = ?
            ''', (candidate_id,))
            c.execute('''
                INSERT INTO activity_logs (candidate_id, action, details)
                VALUES (?, 'Candidate Replied', 'Candidate responded to outreach; Sequence paused automatically')
            ''', (candidate_id,))
        elif action == 'pause':
            c.execute('''
                UPDATE candidates 
                SET sequence_status = 'Paused',
                    last_activity = 'Sequence paused manually by recruiter'
                WHERE id = ?
            ''', (candidate_id,))

        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode('utf-8'))

    def create_job(self, data):
        title = data.get('title')
        dept = data.get('department')
        loc = data.get('location')
        skills = data.get('required_skills')
        min_exp = int(data.get('min_experience', 0))

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO jobs (title, department, location, required_skills, min_experience)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, dept, loc, skills, min_exp))
        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode('utf-8'))

if __name__ == '__main__':
    init_db()
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print(f"TalentFlow AI App serving at http://localhost:{PORT}")
        httpd.serve_forever()
