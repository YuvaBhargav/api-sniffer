import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#8b949e"))
        
        # Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 750, "API Sniffer Engine — Low-Level Design (LLD) & Architecture")
            self.setStrokeColor(colors.HexColor("#21262d"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer (all pages)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_text)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — API SNIFFER PROJECT")
        self.setStrokeColor(colors.HexColor("#21262d"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()

def build_pdf(pdf_filename="API_Sniffer_LLD_Architecture.pdf"):
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    c_primary = colors.HexColor("#0b0e14")
    c_accent = colors.HexColor("#1f6feb")
    c_subtext = colors.HexColor("#484f58")
    c_border = colors.HexColor("#d0d7de")

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0969da"),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_subtext,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0969da"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1f6feb"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#24292f"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0969da"),
        backColor=colors.HexColor("#f6f8fa"),
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8
    )

    story = []

    # Document Header / Title
    story.append(Paragraph("🛰️ API Request Sniffer Engine", title_style))
    story.append(Paragraph("Low-Level Design (LLD) & System Architecture Specification | v2.0", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0969da"), spaceAfter=15))

    # Metadata Block Table
    meta_data = [
        [Paragraph("<b>System Target:</b> PythonAnywhere WSGI / Docker / Render", body_style), Paragraph("<b>Version:</b> 2.0 (IST Timezone)", body_style)],
        [Paragraph("<b>Author:</b> Engineering Team & Antigravity AI", body_style), Paragraph("<b>Storage Mode:</b> Zero-Disk Base64 SQLite Engine", body_style)],
        [Paragraph("<b>Status:</b> Approved & Production Ready", body_style), Paragraph("<b>Date:</b> September 2026", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[250, 250])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f6f8fa")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e1e4e8")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Section 1: Executive Summary
    story.append(Paragraph("1. Executive Summary & System Goals", h1_style))
    story.append(Paragraph(
        "The <b>API Request Sniffer Engine</b> is a lightweight, high-performance, self-hosted request inspection and query generator platform. "
        "It provides real-time capture, un-redacted logging, and visual inspection of incoming HTTP requests across all standard methods "
        "(<code>GET</code>, <code>POST</code>, <code>PUT</code>, <code>DELETE</code>, <code>PATCH</code>, <code>OPTIONS</code>, <code>HEAD</code>, <code>TRACE</code>).",
        body_style
    ))
    story.append(Paragraph("<b>Core System Objectives:</b>", h2_style))
    story.append(Paragraph("• <b>Un-redacted Logging:</b> Complete capture of HTTP headers, raw query strings, JSON payloads, form data, client IP, and cookies without masking.", bullet_style))
    story.append(Paragraph("• <b>IST Timezone Standardization:</b> Native formatting of all log timestamps in Indian Standard Time (<code>UTC+5:30</code>).", bullet_style))
    story.append(Paragraph("• <b>Zero-Disk Storage Mode:</b> Multipart file uploads are Base64 encoded into Data URIs and stored directly in SQLite, eliminating disk quota usage on platforms like PythonAnywhere.", bullet_style))
    story.append(Paragraph("• <b>Multi-Language Query Generator:</b> Built-in generator capable of constructing ready-to-run queries across 6 data modes in cURL, Python (requests), JavaScript (fetch), and PowerShell.", bullet_style))
    story.append(Paragraph("• <b>Minimalist Zero-Lag UI:</b> Single-page dark dashboard featuring instant search filtering, real-time polling, and interactive in-browser request execution.", bullet_style))

    story.append(Spacer(1, 10))

    # Section 2: High Level Architecture
    story.append(Paragraph("2. System High-Level Architecture", h1_style))
    story.append(Paragraph(
        "The architecture is decoupled into three core layers: an Ingestion/WSGI Server Layer, a SQLite Connection Pool Storage Layer, and a Client Dashboard SPA featuring a multi-language query builder.",
        body_style
    ))
    
    if os.path.exists("arch_diagram.png"):
        story.append(Spacer(1, 4))
        story.append(Image("arch_diagram.png", width=490, height=240))
        story.append(Spacer(1, 8))

    story.append(PageBreak())

    # Section 3: Low-Level Component Design
    story.append(Paragraph("3. Low-Level Component Design (LLD)", h1_style))
    
    story.append(Paragraph("3.1 Ingestion & Listener Layer (app.py)", h2_style))
    story.append(Paragraph(
        "The ingestion layer is implemented using Flask wildcard routes (<code>@flask_app.route('/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD', 'TRACE'])</code>). "
        "It inspects every incoming request object and extracts raw attributes without truncation.",
        body_style
    ))
    story.append(Paragraph(
        "<b>File Handling Subsystem:</b> Incoming files are read directly into memory from <code>request.files</code>, hashed with MD5, and converted into Base64 Data URIs: "
        "<code>data:{content_type};base64,{b64_str}</code>. This guarantees zero byte output to server disk storage.",
        body_style
    ))

    story.append(Paragraph("3.2 Persistence Layer (db.py)", h2_style))
    story.append(Paragraph(
        "The database module manages an SQLite backend (<code>sniffer_logs.db</code>) using a thread-safe connection pool with write locks. "
        "All data models are serialized to JSON strings prior to insertion.",
        body_style
    ))

    story.append(Paragraph("3.3 Multi-Language Query Generator Engine", h2_style))
    story.append(Paragraph(
        "The client-side generator dynamically builds code snippets for 6 identifier types: JSON Payload, Raw Text Body, File Upload, Query Parameters, Form Data, and Empty Requests. "
        "The generator supports four target environments:",
        body_style
    ))
    story.append(Paragraph("• <b>cURL:</b> Standard CLI syntax with appropriate <code>-H</code> headers and <code>-d</code> / <code>-F</code> flags.", bullet_style))
    story.append(Paragraph("• <b>Python:</b> Native <code>requests</code> code using <code>json=</code>, <code>data=</code>, or <code>files=</code> parameters.", bullet_style))
    story.append(Paragraph("• <b>JavaScript:</b> Modern <code>fetch()</code> API with async promise resolution.", bullet_style))
    story.append(Paragraph("• <b>PowerShell:</b> <code>Invoke-RestMethod</code> cmdlet string formatting.", bullet_style))

    story.append(Spacer(1, 10))

    # Section 4: Database Schema Table
    story.append(Paragraph("4. Database Schema Specification", h1_style))
    story.append(Paragraph("Table: <code>sniffer_logs</code>", h2_style))

    schema_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    schema_rows = [
        [schema_headers[0], schema_headers[1], schema_headers[2], schema_headers[3]],
        ["id", "INTEGER", "PRIMARY KEY AUTOINCREMENT", "Unique internal log ID"],
        ["request_id", "TEXT", "NOT NULL, UNIQUE", "UUID v4 string for tracking"],
        ["timestamp", "TEXT", "NOT NULL", "IST formatted string (YYYY-MM-DD HH:MM:SS)"],
        ["method", "TEXT", "NOT NULL", "HTTP Method (GET, POST, PUT, etc.)"],
        ["url", "TEXT", "NOT NULL", "Full incoming URL with query string"],
        ["path", "TEXT", "NOT NULL", "URL path component"],
        ["query_params", "TEXT (JSON)", "DEFAULT '{}'", "Parsed query key-value pairs"],
        ["headers", "TEXT (JSON)", "NOT NULL", "Un-redacted HTTP request headers"],
        ["body_type", "TEXT", "NOT NULL", "payload / text / file / form / empty"],
        ["body", "TEXT", "DEFAULT ''", "Raw body or formatted JSON string"],
        ["files", "TEXT (JSON)", "DEFAULT '[]'", "Base64 data URIs, MD5, metadata"],
        ["client_ip", "TEXT", "NOT NULL", "Remote IP address of caller"]
    ]

    t_schema = Table([[Paragraph(f"<b>{c}</b>", body_style) if idx==0 else Paragraph(c, body_style) for c in row] for idx, row in enumerate(schema_rows)], colWidths=[90, 95, 145, 170])
    t_schema.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0969da")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e1e4e8")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ffffff")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f6f8fa")]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_schema)

    story.append(Spacer(1, 10))

    # Section 5: Sequence Diagram & Execution Flow
    story.append(Paragraph("5. Processing Sequence & Data Flow", h1_style))
    story.append(Paragraph(
        "When an external API call or test request is executed, it traverses the WSGI listener, parses multipart parameters into Base64, "
        "persists the payload into SQLite with an IST timestamp, and triggers client-side polling update.",
        body_style
    ))

    if os.path.exists("seq_diagram.png"):
        story.append(Spacer(1, 4))
        story.append(Image("seq_diagram.png", width=490, height=210))
        story.append(Spacer(1, 8))

    # Section 6: Deployment & Security Architecture
    story.append(Paragraph("6. Deployment & Environment Strategy", h1_style))
    story.append(Paragraph("<b>PythonAnywhere WSGI Configuration:</b>", h2_style))
    story.append(Paragraph("The application runs on PythonAnywhere via WSGI entrypoint forwarding directly to <code>app.py:flask_app</code> without binding background web ports, preserving worker pool safety.", body_style))
    
    story.append(Paragraph("<b>Docker Containerization:</b>", h2_style))
    story.append(Paragraph("A lightweight multi-stage Docker build is provided for containerized deployments on Render, Railway, or local environments:", body_style))
    
    docker_snippet = """# Dockerfile snippet
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]"""
    story.append(Paragraph(docker_snippet.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))

    # Section 7: Verification & Testing Summary
    story.append(Paragraph("7. Verification Matrix & Synthetic Test Suite", h1_style))
    story.append(Paragraph("The system includes an automated synthetic test suite (<code>test_sniffer.py</code>) verifying all 7 core method variants:", body_style))

    test_results = [
        ["Test Case", "Method / Payload", "Expected Result", "Status"],
        ["1. Query String", "GET /api/v1/test?event=test", "200 OK, Parsed Params logged", "PASS"],
        ["2. JSON Body", "POST /api/v1/test (application/json)", "200 OK, Payload logged", "PASS"],
        ["3. Raw Text", "PUT /api/v1/test (text/plain)", "200 OK, Raw Text logged", "PASS"],
        ["4. Resource Patch", "PATCH /api/v1/test", "200 OK, State updated", "PASS"],
        ["5. Delete Request", "DELETE /api/v1/test", "200 OK, Deletion captured", "PASS"],
        ["6. Preflight", "OPTIONS /api/v1/test", "200 OK, Headers parsed", "PASS"],
        ["7. File Upload", "POST Multipart File Upload", "200 OK, Base64 URI saved", "PASS"]
    ]

    t_tests = Table([[Paragraph(f"<b>{c}</b>", body_style) if idx==0 else Paragraph(c, body_style) for c in row] for idx, row in enumerate(test_results)], colWidths=[100, 160, 170, 70])
    t_tests.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f6feb")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e1e4e8")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f6f8fa")]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tests)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"LLD PDF document successfully generated: {pdf_filename}")

if __name__ == "__main__":
    build_pdf()
