from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import os
import json
import sqlite3
from datetime import datetime
import anthropic
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database initialization
DB_PATH = 'recruitment_interviews.db'

def init_db():
      """Initialize SQLite database with required tables."""
      conn = sqlite3.connect(DB_PATH)
      c = conn.cursor()

    # Conversations table
      c.execute('''CREATE TABLE IF NOT EXISTS conversations
                   (id TEXT PRIMARY KEY,
                    physician_name TEXT,
                    specialty TEXT,
                    timestamp DATETIME,
                    interview_transcript TEXT,
                    skills JSON,
                    interests JSON,
                    wants_needs JSON,
                    location_state TEXT,
                    compensation_expectations TEXT,
                    start_timeline TEXT,
                    report_generated BOOLEAN)''')

    # Jobs table
      c.execute('''CREATE TABLE IF NOT EXISTS jobs
                   (id TEXT PRIMARY KEY,
                    title TEXT,
                    location TEXT,
                    state TEXT,
                    specialty TEXT,
                    source TEXT,
                    url TEXT,
                    salary_range TEXT,
                    last_updated DATETIME)''')

    conn.commit()
    conn.close()

init_db()

# Initialize Anthropic client
claude_client = anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY', 'placeholder')) if os.getenv('CLAUDE_API_KEY') else None
@app.route('/webhook/conversation-ended', methods=['POST'])
def webhook_conversation_ended():
      """Receive webhook from ElevenLabs when conversation ends."""
      try:
                data = request.json
                conversation_id = data.get('conversation_id')
                transcript = data.get('transcript', '')

        # Process transcript with Claude
                analysis = process_transcript(transcript)

        # Store in database
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()

        c.execute('''INSERT INTO conversations 
                             (id, physician_name, specialty, timestamp, interview_transcript, 
                                                   skills, interests, wants_needs, location_state, compensation_expectations,
                                                                         start_timeline, report_generated)
                                                                                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                    (conversation_id,
                                                        analysis.get('name', 'Unknown'),
                                                        'Pulmonary & Critical Care',
                                                        datetime.now(),
                                                        transcript,
                                                        json.dumps(analysis.get('skills', [])),
                                                        json.dumps(analysis.get('interests', [])),
                                                        json.dumps(analysis.get('wants_needs', {})),
                                                        analysis.get('location_state', ''),
                                                        analysis.get('compensation', ''),
                                                        analysis.get('timeline', ''),
                                                        True))

        conn.commit()
        conn.close()

        # Generate PDF report
        generate_pdf_report(conversation_id, analysis)

        return jsonify({'status': 'success', 'conversation_id': conversation_id}), 200

except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_transcript(transcript):
      """Use Claude to analyze interview transcript."""
      prompt = f"""Analyze this physician interview transcript and extract the following information:
      1. Physician name
      2. Clinical skills mentioned
      3. Professional interests
      4. Location preferences (state)
      5. Compensation expectations
      6. Start timeline preferences
      7. Specialty-specific wants and needs

      Format response as JSON with keys: name, skills (list), interests (list), location_state (string), 
      compensation (string), timeline (string), wants_needs (dict).

      Transcript:
      {transcript}
      """

    message = claude_client.messages.create(
              model="claude-3-5-sonnet-20241022",
              max_tokens=1024,
              messages=[
                            {"role": "user", "content": prompt}
              ]
    )

    try:
              response_text = message.content[0].text
              # Extract JSON from response
              start = response_text.find('{')
              end = response_text.rfind('}') + 1
              if start != -1 and end > start:
                            analysis = json.loads(response_text[start:end])
    else:
            analysis = {
                              'name': 'Unknown',
                              'skills': [],
                              'interests': [],
                              'location_state': '',
                              'compensation': '',
                              'timeline': '',
                              'wants_needs': {}
            }
          except:
        analysis = {
                      'name': 'Unknown',
                      'skills': [],
                      'interests': [],
                      'location_state': '',
                      'compensation': '',
                      'timeline': '',
                      'wants_needs': {}
        }

                return analysis

def generate_pdf_report(conversation_id, analysis):
      """Generate comprehensive PDF report for physician candidate."""
    try:
              pdf_filename = f"reports/{conversation_id}_report.pdf"

        # Create PDF
              doc = SimpleDocTemplate(pdf_filename, pagesize=letter,
                                     rightMargin=72, leftMargin=72,
                                     topMargin=72, bottomMargin=18)

        # Container for PDF elements
              elements = []

        # Styles
              styles = getSampleStyleSheet()
              title_style = ParagraphStyle(
                  'CustomTitle',
                  parent=styles['Heading1'],
                  fontSize=24,
                  textColor=colors.HexColor('#1f4788'),
                  spaceAfter=30,
                  alignment=1
              )

        # Title
              elements.append(Paragraph(f"Physician Recruitment Report", title_style))
              elements.append(Spacer(1, 0.3*inch))

        # Candidate Information
              elements.append(Paragraph("Candidate Information", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        info_data = [
                      ['Name:', analysis.get('name', 'N/A')],
                      ['Specialty:', 'Pulmonary & Critical Care Medicine'],
                      ['Location Preference:', analysis.get('location_state', 'N/A')],
                      ['Compensation Expectations:', analysis.get('compensation', 'N/A')],
                      ['Start Timeline:', analysis.get('timeline', 'N/A')]
        ]

        info_table = Table(info_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
                      ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
                      ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                      ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                      ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                      ('FONTSIZE', (0, 0), (-1, -1), 10),
                      ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                      ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 0.3*inch))

        # Clinical Skills
        elements.append(Paragraph("Clinical Skills & Expertise", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        skills = analysis.get('skills', [])
        if skills:
                      for skill in skills:
                                        elements.append(Paragraph(f"• {skill}", styles['Normal']))
        else:
            elements.append(Paragraph("No skills specified", styles['Normal']))

                  elements.append(Spacer(1, 0.2*inch))

        # Professional Interests
        elements.append(Paragraph("Professional Interests", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        interests = analysis.get('interests', [])
        if interests:
                      for interest in interests:
                                        elements.append(Paragraph(f"• {interest}", styles['Normal']))
        else:
            elements.append(Paragraph("No interests specified", styles['Normal']))

        elements.append(Spacer(1, 0.2*inch))

        # Wants & Needs
        elements.append(Paragraph("Specialty-Specific Wants & Needs", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        wants_needs = analysis.get('wants_needs', {})
        if wants_needs:
                      for key, value in wants_needs.items():
                                        elements.append(Paragraph(f"<b>{key}:</b> {value}", styles['Normal']))
        else:
            elements.append(Paragraph("No specific wants/needs identified", styles['Normal']))

        elements.append(Spacer(1, 0.3*inch))

        # Matching Opportunities
        elements.append(PageBreak())
        elements.append(Paragraph("Matching Opportunities", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))

        # Get matching jobs
        matching_jobs = get_matching_jobs(analysis.get('location_state', ''))
        if matching_jobs:
                      for job in matching_jobs[:5]:  # Top 5 matches
                          elements.append(Paragraph(f"<b>{job['title']}</b>", styles['Normal']))
                                        elements.append(Paragraph(f"Location: {job['location']}", styles['Normal']))
                                        elements.append(Paragraph(f"Source: {job['source']}", styles['Normal']))
                                        elements.append(Spacer(1, 0.1*inch))
        else:
            elements.append(Paragraph("No matching opportunities at this time", styles['Normal']))

        # Report Footer
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                                                                   styles['Normal']))
        elements.append(Paragraph("Pulmonary & Critical Care Recruitment System", styles['Normal']))

        # Build PDF
        doc.build(elements)

        return pdf_filename

except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

def get_matching_jobs(state):
      """Retrieve matching jobs for candidate by state."""
    try:
              conn = sqlite3.connect(DB_PATH)
              conn.row_factory = sqlite3.Row
              c = conn.cursor()

        c.execute('''SELECT * FROM jobs 
                             WHERE state = ? AND specialty = 'Pulmonary & Critical Care'
                                       ORDER BY last_updated DESC LIMIT 10''', (state,))

        jobs = [dict(row) for row in c.fetchall()]
        conn.close()

        return jobs
    except:
        return []

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
      """Retrieve all interview conversations."""
    try:
              conn = sqlite3.connect(DB_PATH)
              conn.row_factory = sqlite3.Row
              c = conn.cursor()

        c.execute('SELECT id, physician_name, timestamp, specialty FROM conversations ORDER BY timestamp DESC')
        conversations = [dict(row) for row in c.fetchall()]
        conn.close()

        return jsonify(conversations), 200
except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/<conversation_id>', methods=['GET'])
def get_report(conversation_id):
      """Download PDF report for interview."""
    try:
              pdf_path = f"reports/{conversation_id}_report.pdf"
              if os.path.exists(pdf_path):
                            return send_file(pdf_path, mimetype='application/pdf', as_attachment=True,
                                                                        download_name=f"{conversation_id}_report.pdf")
    else:
            return jsonify({'error': 'Report not found'}), 404
except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs/matching', methods=['POST'])
def get_matching():
      """Get matching jobs based on candidate profile."""
    try:
              data = request.json
              state = data.get('state', '')
              jobs = get_matching_jobs(state)
              return jsonify({'matching_jobs': jobs}), 200
except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/jobs/refresh', methods=['POST'])
def refresh_jobs():
      """Manually trigger job refresh from sources."""
    try:
              from jobs_scraper import JobScraper
              scraper = JobScraper()
              scraper.refresh_jobs()
              return jsonify({'status': 'success', 'message': 'Jobs refreshed'}), 200
except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
      """Real-time recruitment dashboard."""
    html = """
        <!DOCTYPE html>
            <html>
                <head>
                        <title>Recruitment Avatar Dashboard</title>
                                <style>
                                            * { margin: 0; padding: 0; box-sizing: border-box; }
                                                        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }
                                                                    .container { max-width: 1200px; margin: 0 auto; }
                                                                                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
                                                                                            .header h1 { font-size: 32px; margin-bottom: 10px; }
                                                                                                        .header p { opacity: 0.9; }
                                                                                                                    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
                                                                                                                                .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                                                                                                                                            .stat-card h3 { color: #333; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; }
                                                                                                                                                        .stat-card .value { font-size: 32px; font-weight: bold; color: #667eea; }
                                                                                                                                                                    .interviews { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                                                                                                                                                                                .interviews h2 { margin-bottom: 20px; color: #333; }
                                                                                                                                                                                            .interview-item { padding: 15px; border-left: 4px solid #667eea; background: #f9f9f9; margin-bottom: 10px; border-radius: 4px; }
                                                                                                                                                                                                        .interview-item .name { font-weight: bold; color: #333; }
                                                                                                                                                                                                                    .interview-item .time { font-size: 12px; color: #999; }
                                                                                                                                                                                                                                .interview-item .action { margin-top: 10px; }
                                                                                                                                                                                                                                            .btn { padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; font-size: 12px; }
                                                                                                                                                                                                                                                        .btn:hover { background: #764ba2; }
                                                                                                                                                                                                                                                                    .refresh-btn { position: fixed; bottom: 20px; right: 20px; padding: 15px 25px; background: #667eea; color: white; border: none; border-radius: 50px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2); font-weight: bold; }
                                                                                                                                                                                                                                                                                .refresh-btn:hover { background: #764ba2; }
                                                                                                                                                                                                                                                                                        </style>
                                                                                                                                                                                                                                                                                            </head>
                                                                                                                                                                                                                                                                                                <body>
                                                                                                                                                                                                                                                                                                        <div class="container">
                                                                                                                                                                                                                                                                                                                    <div class="header">
                                                                                                                                                                                                                                                                                                                                    <h1>Physician Recruitment Dashboard</h1>
                                                                                                                                                                                                                                                                                                                                                    <p>AI-powered interview processing and job matching system</p>
                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                        <div class="stats">
                                                                                                                                                                                                                                                                                                                                                                                                        <div class="stat-card">
                                                                                                                                                                                                                                                                                                                                                                                                                            <h3>Total Interviews</h3>
                                                                                                                                                                                                                                                                                                                                                                                                                                                <div class="value" id="total-interviews">0</div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                <div class="stat-card">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <h3>Reports Generated</h3>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <div class="value" id="reports-generated">0</div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <div class="stat-card">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            <h3>Active Candidates</h3>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                <div class="value" id="active-candidates">0</div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <div class="interviews">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <h2>Recent Interviews</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <div id="interviews-list"></div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <button class="refresh-btn" onclick="location.reload()">Refresh</button>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <script>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    async function loadData() {
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    try {
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        const response = await fetch('/api/conversations');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            const conversations = await response.json();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    document.getElementById('total-interviews').textContent = conversations.length;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        document.getElementById('reports-generated').textContent = conversations.length;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            document.getElementById('active-candidates').textContent = conversations.length;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    const list = document.getElementById('interviews-list');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        list.innerHTML = '';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                conversations.slice(0, 10).forEach(conv => {
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        const item = document.createElement('div');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                item.className = 'interview-item';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        const timestamp = new Date(conv.timestamp).toLocaleString();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                item.innerHTML = `
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            <div class="name">${conv.physician_name}</div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <div class="time">${timestamp}</div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <div class="action">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <a href="/api/report/${conv.id}" class="btn">Download Report</a>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        `;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                list.appendChild(item);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    });
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            if (conversations.length === 0) {
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    list.innerHTML = '<p style="color: #999;">No interviews yet</p>';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        } catch (error) {
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            console.error('Error loading data:', error);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                loadData();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            setInterval(loadData, 30000); // Refresh every 30 seconds
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    </script>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </body>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            </html>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                """
    return render_template_string(html)

@app.route('/health', methods=['GET'])
def health():
      """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['GET'])
def index():
      """Root endpoint with API documentation."""
    return jsonify({
              'service': 'Recruitment Avatar Backend',
              'version': '1.0.0',
              'endpoints': {
                            'POST /webhook/conversation-ended': 'Receive completed interview from ElevenLabs',
                            'GET /api/conversations': 'List all interviews',
                            'GET /api/report/<id>': 'Download PDF report',
                            'POST /api/jobs/matching': 'Get matching job opportunities',
                            'POST /api/jobs/refresh': 'Refresh job listings',
                            'GET /dashboard': 'View recruitment dashboard',
                            'GET /health': 'Health check'
              }
    }), 200

if __name__ == '__main__':
      os.makedirs('reports', exist_ok=True)
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
