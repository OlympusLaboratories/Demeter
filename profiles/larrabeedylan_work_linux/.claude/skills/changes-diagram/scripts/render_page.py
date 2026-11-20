"""Inject build_changes_graph.py JSON into template.html. Usage: render_page.py <graph.json> <template.html> <out.html>"""
import sys
from pathlib import Path

data, template, out = sys.argv[1:4]
payload = Path(data).read_text().replace("</", "<\\/")
Path(out).write_text(Path(template).read_text().replace("/*MR_DATA*/", payload))
