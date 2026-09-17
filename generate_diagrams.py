import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_architecture_diagram():
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis('off')
    
    # Background
    fig.patch.set_facecolor('#0b0e14')
    ax.set_facecolor('#0b0e14')

    # Draw Boxes
    def add_box(x, y, w, h, title, subtitle, color, border_color):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1,rounding_size=2",
                                     linewidth=1.5, edgecolor=border_color, facecolor=color)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2 + 2, title, color='#ffffff', weight='bold', fontsize=10, ha='center', va='center')
        ax.text(x + w/2, y + h/2 - 3, subtitle, color='#8b949e', fontsize=8, ha='center', va='center')

    # Component 1: Clients & Sources
    add_box(5, 38, 20, 16, "API Clients & cURL", "cURL / Postman / Mobile / Web", "#161b22", "#388bfd")
    add_box(5, 10, 20, 16, "Web Dashboard UI", "HTML5 / JS SPA / Dark Theme", "#161b22", "#56d364")

    # Component 2: Ingestion & Server Layer
    add_box(38, 24, 24, 20, "Flask WSGI Server (app.py)", "Wildcard Listener / Catch-all\nUn-redacted Parser (IST)", "#161b22", "#bc8cff")

    # Component 3: Storage & Generator Layer
    add_box(72, 38, 23, 16, "SQLite Database (db.py)", "Thread-Safe Connection Pool\nBase64 Zero-Disk Storage", "#161b22", "#e3b341")
    add_box(72, 10, 23, 16, "Query Generator Engine", "6 Data Modes\ncURL/Py/JS/PS Snippets", "#161b22", "#f85149")

    # Arrow connections
    def add_arrow(x1, y1, x2, y2, label=""):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#58a6ff", lw=1.5))
        if label:
            ax.text((x1 + x2)/2, (y1 + y2)/2 + 1.5, label, color='#8b949e', fontsize=7, ha='center')

    add_arrow(26, 46, 37, 38, "HTTP/HTTPS Requests")
    add_arrow(26, 18, 37, 30, "Send Test / Poll Logs")
    add_arrow(63, 36, 71, 46, "Store Logs & Base64 Files")
    add_arrow(63, 30, 71, 18, "Generate Snippets")

    # Title
    ax.text(50, 56, "API Sniffer Engine - High-Level Architecture Diagram", color='#ffffff', weight='bold', fontsize=13, ha='center')

    plt.tight_layout()
    diagram_path = "arch_diagram.png"
    plt.savefig(diagram_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return diagram_path

def draw_sequence_diagram():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis('off')
    
    fig.patch.set_facecolor('#0b0e14')
    ax.set_facecolor('#0b0e14')

    # Vertical lifelines
    lifelines = {
        "Client": 15,
        "Flask Listener": 40,
        "Base64 Parser": 65,
        "SQLite Pool": 90
    }

    for name, x in lifelines.items():
        ax.plot([x, x], [10, 50], color='#30363d', linestyle='--', lw=1)
        rect = patches.FancyBboxPatch((x-10, 50), 20, 6, boxstyle="round,pad=0.5", linewidth=1, edgecolor='#58a6ff', facecolor='#161b22')
        ax.add_patch(rect)
        ax.text(x, 53, name, color='#ffffff', weight='bold', fontsize=9, ha='center')

    # Sequence calls
    calls = [
        (15, 40, 44, "1. HTTP Request (GET/POST/PUT/Upload)", "#58a6ff"),
        (40, 65, 36, "2. Parse Headers & Encode Multipart Base64", "#bc8cff"),
        (65, 90, 28, "3. Insert Record with IST Timestamp", "#e3b341"),
        (90, 40, 20, "4. Return Status 200 & Request ID", "#56d364"),
        (40, 15, 12, "5. Response + Live Feed Refresh", "#58a6ff")
    ]

    for x1, x2, y, label, color in calls:
        ax.annotate('', xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.3))
        ax.text((x1 + x2)/2, y + 1.5, label, color='#e6edf3', fontsize=7.5, ha='center')

    ax.text(50, 57, "Incoming API Request Processing & Zero-Disk Storage Sequence", color='#ffffff', weight='bold', fontsize=12, ha='center')

    plt.tight_layout()
    diagram_path = "seq_diagram.png"
    plt.savefig(diagram_path, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return diagram_path

if __name__ == "__main__":
    p1 = draw_architecture_diagram()
    p2 = draw_sequence_diagram()
    print(f"Diagrams generated: {p1}, {p2}")
