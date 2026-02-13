import requests
import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
import pickle
from io import BytesIO
from django.conf import settings



# import googleapiclient.errors
import re
import unicodedata

# PDF deps
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import configparser

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


# =========================
# Config / Secrets
# =========================
cfg = configparser.ConfigParser()
cfg.read("secretKeys.ini")
FANIKIWA_URL = cfg.get("Credentials", "FANIKIWA_URL")

SANCTIONS_FANIKIWA_API_KEY_PROD = cfg.get("Credentials", "SANCTIONS_FANIKIWA_API_KEY_PROD")

Ofac_ApiKey = cfg.get("Credentials", "OFAC_API_KEY")

gmail_credentials_compliance = Path().absolute()/'sanctionScreeningFanikiwa/services/gmail_credentials_compliance.json'



class UnifiedSanctionsBot:
    def __init__(self):
        """Initialize the unified sanctions bot with all sources"""
        # OFAC API setup (using your working API)
        self.ofac_api_key = Ofac_ApiKey
        self.ofac_url = "https://api.ofac-api.com/v4/screen"

        self.eu_url = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content?token=dG9rZW4tMjAxNw"
        self.eu_file = "eu_sanctions.csv"

        self.un_url = "https://scsanctions.un.org/consolidated"
        self.un_file = "un_sanctions.html"

        self.uk_url = "https://docs.fcdo.gov.uk/docs/UK-Sanctions-List.html"
        self.uk_file = "uk_sanctions.html"

        # Workflow configuration
        self.min_score_threshold = 100  # Default minimum score for OFAC API
        self.compliance_email = "risk.compliance@fmfc.co.tz"
        self.credit_email = "creditadmin@fmfc.co.tz"

        # Mambu API configuration
        self.mambu_base_url = FANIKIWA_URL
        self.mambu_api_key = SANCTIONS_FANIKIWA_API_KEY_PROD

    
    
    def generate_pdf_report_bytes(self, query: str, match: dict, client_id: str = "", owner_type: str = "CLIENT") -> bytes:
        """Generate a single-match PDF report and return raw PDF bytes."""
        buf = BytesIO()

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            title="Sanctions Screening Report",
            author="UnifiedSanctionsBot",
        )

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        normal = styles["BodyText"]
        heading = styles["Heading2"]

        elements = []
        elements.append(Paragraph("Sanctions Screening Report", title_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal))
        elements.append(Paragraph(f"Search Query: {query}", normal))
        elements.append(Paragraph(f"Owner Type: {owner_type}", normal))
        if client_id:
            elements.append(Paragraph(f"Client/Loan ID: {client_id}", normal))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Match Details", heading))

        source = match.get("source") or "N/A"
        name = match.get("name") or "N/A"
        mtype = match.get("type") or "N/A"
        programs = match.get("programs")
        if isinstance(programs, list):
            programs = ", ".join(programs)
        programs = programs or "N/A"
        score = match.get("score")
        score = str(score) if score is not None else "N/A"
        details = match.get("match_details") or match.get("addresses") or "N/A"

        data = [
            ["Field", "Value"],
            ["Source", source],
            ["Name", name],
            ["Type", mtype],
            ["Programs", programs],
            ["Score", score],
            ["Additional Info", str(details)],
        ]

        tbl = Table(data, colWidths=[110, 430])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        elements.append(tbl)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Compliance Note", heading))
        elements.append(
            Paragraph(
                "This report is generated automatically based on sanctions screening results. "
                "If the score and details indicate a potential match, manual compliance review is required.",
                normal,
            )
        )

        doc.build(elements)
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes

    
    def generate_combined_pdf_report_bytes(self, query: str, results: list, matches_found=None, client_id: str = "", owner_type: str = "CLIENT") -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, title="Unified Sanctions Search Report")

        styles = getSampleStyleSheet()
        title = styles["Title"]
        h2 = styles["Heading2"]
        body = styles["BodyText"]

        # Group results by source
        grouped = {}
        for r in (results or []):
            src = r.get("source") or "UNKNOWN"
            grouped.setdefault(src, []).append(r)

        # Sources list like your TXT report
        sources_list = ", ".join(grouped.keys()) if grouped else "N/A"
        total_results = len(results or [])

        elems = []
        elems.append(Paragraph("UNIFIED SANCTIONS SEARCH REPORT", title))
        elems.append(Spacer(1, 10))
        elems.append(Paragraph(f"Search Query: {query}", body))
        elems.append(Paragraph(f"Client/Loan ID: {client_id or 'None'}", body))
        elems.append(Paragraph(f"Owner Type: {owner_type}", body))
        elems.append(Paragraph(f"Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body))
        elems.append(Paragraph(f"Total Results: {total_results}", body))
        if matches_found is not None:
            elems.append(Paragraph(f"Matches Found (backend): {matches_found}", body))
        elems.append(Paragraph(f"Sources Searched: {sources_list}", body))
        elems.append(Spacer(1, 14))

        # Recommendation block
        if total_results > 0:
            elems.append(Paragraph("⚠ SANCTIONS MATCHES FOUND — COMPLIANCE REVIEW REQUIRED", h2))
        else:
            elems.append(Paragraph("No sanctions matches found.", h2))
        elems.append(Spacer(1, 10))

        # Per-source sections
        for src, items in grouped.items():
            elems.append(Paragraph(f"{src} SANCTIONS DATABASE RESULTS", h2))
            elems.append(Paragraph(f"Results found: {len(items)}", body))
            elems.append(Spacer(1, 8))

            for idx, r in enumerate(items, start=1):
                name = r.get("name") or "N/A"
                typ = r.get("type") or "N/A"
                programs = r.get("programs") or "N/A"
                if isinstance(programs, list):
                    programs = ", ".join(programs) if programs else "N/A"

                score = r.get("score")
                score = str(score) if score is not None else "N/A"

                info = r.get("match_details") or r.get("additional_info") or r.get("addresses") or "N/A"

                data = [
                    ["Field", "Value"],
                    ["Source", src],
                    ["Name", str(name)],
                    ["Type", str(typ)],
                    ["Programs", str(programs)],
                    ["Match Score", str(score)],
                    ["Additional Info", str(info)],
                ]

                t = Table(data, colWidths=[110, 430])
                t.setStyle

    # ---------------------------
    # Helper functions
    # ---------------------------
    def _prep_query_words(self, query):
        """Lowercase, split, and filter short tokens (<=2 chars)."""
        return [w.lower().strip() for w in query.split() if len(w.strip()) > 2]

    def _count_full_word_matches(self, text, query_words):
        """Return how many DISTINCT query words appear as full words in the text."""
        found = set()
        tlow = text.lower()
        for w in query_words:
            if not w:
                continue
            if re.search(r'\b' + re.escape(w) + r'\b', tlow):
                found.add(w)
        return len(found)

    def _normalize_name(self, s: str) -> str:
        """Lowercase, strip, collapse spaces, remove accents & most punctuation for stable comparisons."""
        if not s:
            return ""
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _full_name_regex(self, full_name: str) -> re.Pattern:
        """
        Build a tolerant regex for the full name:
        - word boundaries around the whole name
        - allow 1+ spaces or punctuation between tokens
        """
        tokens = [re.escape(t) for t in re.split(r"\s+", full_name.strip()) if t]
        sep = r"[\s\W]+"
        pattern = r"\b" + sep.join(tokens) + r"\b"
        return re.compile(pattern, flags=re.IGNORECASE)

    # ---------------------------
    # Source searches
    # ---------------------------
    def search_ofac(self, query, client_id, recipient_id):
        """Search OFAC sanctions and return results only if the name matches exactly (100%)."""
        import json, requests

        print("🔍 Searching OFAC database...")
        results = []

        if not self.ofac_api_key:
            print("❌ OFAC API key not found")
            return []

        try:
            payload = json.dumps({
                "apiKey": self.ofac_api_key,
                "includeAlias": "true",
                "type": ["person"],
                "minScore": self.min_score_threshold,
                "sources": [
                    "SDN", "NONSDN", "FINCEN", "DPL", "UN", "FSF", "BFS",
                    "OFSI", "DNSL", "SECO", "SEMA", "DFAT", "HUD", "SAM",
                    "FHFA", "US", "EU"
                ],
                "cases": [
                    {
                        "name": query,
                        "identification": [{"idNumber": recipient_id}]
                    }
                ]
            })

            headers = {'Content-Type': 'application/json'}
            response = requests.post(self.ofac_url, headers=headers, data=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'results' in data and data['results']:
                    for result_case in data['results']:
                        case_name = result_case.get('name', '').strip().lower()
                        for match in result_case.get('matches', []):
                            sanction = match.get('sanction', {})
                            # sanction_name = sanction.get('name', '').strip().lower()
                            # print("caseName",case_name)
                            # print("sanctionName",sanction_name)
                            
                            # # Normalize both names for a robust comparison
                            # # This handles case, spacing, punctuation, and word order
                            # norm_query = self._normalize_name(query)
                            # norm_sanction_name = self._normalize_name(sanction_name)

                            # # Split into words and compare sets to ignore word order
                            # query_words = set(norm_query.split())
                            # sanction_words = set(norm_sanction_name.split())

                            if int(match['score']) > 93:
                                print("🔍 High score match found:", match['score'])
                                # ✅ Match found, append the result details
                                results.append({
                                    'source': "OFAC",
                                    'name': sanction.get('name', 'N/A'),
                                    'type': sanction.get('type', 'N/A'),
                                    'programs': ', '.join(sanction.get('programs', []) or []),
                                    'addresses': str(sanction.get('personDetails', {}) or {}),
                                    'score': match.get('score', 'N/A'),
                                    'link': sanction.get('entityLink', ''),
                                    'raw_data': match
                                })
                print(f"✅ OFAC: Found {len(results)} exact matches")

            else:
                print(f"❌ OFAC API request failed with status code: {response.status_code}")
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"❌ Error searching OFAC: {e}")

        print("OFAC Results:", results)
        return results

    def download_eu_csv(self):
        """Download EU sanctions CSV file"""
        if os.path.exists(self.eu_file):
            print(f"📂 EU CSV file already exists. Using existing file.")
            return True

        print("⬇️ Downloading EU sanctions CSV...")
        try:
            response = requests.get(self.eu_url, stream=True)
            if response.status_code == 200:
                with open(self.eu_file, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"✅ EU CSV downloaded successfully")
                return True
            else:
                print(f"❌ Failed to download EU CSV. Status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error downloading EU CSV: {e}")
            return False

    def search_eu(self, query, match_mode="tokens"):
        """Search EU sanctions CSV. tokens=≥2 token rule (current), full_name=exact-ish full name."""
        print("🔍 Searching EU database...")
        results = []

        if not self.download_eu_csv():
            return results

        try:
            with open(self.eu_file, "r", encoding="utf-8") as csv_file:
                reader = csv.reader(csv_file, delimiter=";")
                headers = next(reader)

                query_words = self._prep_query_words(query)
                full_norm = self._normalize_name(query)
                full_re = self._full_name_regex(query)

                matches = []
                row_count = 0

                for row in reader:
                    row_count += 1
                    row_dict = dict(zip(headers, row))
                    combined = " | ".join([c for c in row if c])

                    if match_mode == "full_name":
                        # Prefer normalized equality against common name fields
                        name_fields = ['Naal_wholename', 'wholename', 'name', 'full_name', 'entity_name']
                        hit = False
                        for nf in name_fields:
                            nm = row_dict.get(nf, "")
                            if nm and self._normalize_name(nm) == full_norm:
                                hit = True
                                break
                        # If no exact equality in fields, try tolerant regex over the combined line
                        if not hit and full_re.search(combined):
                            hit = True
                        if not hit:
                            continue
                    else:
                        if self._count_full_word_matches(combined, query_words) < 2:
                            continue

                    # --- existing processing / enrichment (kept) ---
                    match_details = []
                    for i, cell in enumerate(row):
                        if not cell:
                            continue
                        cell_count = self._count_full_word_matches(cell, query_words)
                        if cell_count > 0:
                            col = headers[i] if i < len(headers) else f"col_{i}"
                            preview = cell[:80].replace("\n", " ")
                            match_details.append(f"{cell_count} token(s) matched in '{col}': '{preview}...'")
                    row_dict['_match_details'] = match_details

                    # name/program resolution
                    name_fields = ['Naal_wholename', 'wholename', 'name', 'full_name', 'entity_name']
                    firstname_fields = ['Naal_firstname', 'firstname', 'first_name']
                    lastname_fields = ['Naal_lastname', 'lastname', 'last_name']
                    programme_fields = ['Programme', 'programme', 'programs', 'sanctions_programme']

                    name = 'N/A'
                    for field in name_fields:
                        if row_dict.get(field):
                            name = row_dict.get(field)
                            break

                    if name == 'N/A':
                        firstname = ''
                        lastname = ''
                        for field in firstname_fields:
                            if row_dict.get(field):
                                firstname = row_dict.get(field)
                                break
                        for field in lastname_fields:
                            if row_dict.get(field):
                                lastname = row_dict.get(field)
                                break
                        if firstname or lastname:
                            name = f"{firstname} {lastname}".strip()

                    programmes = 'N/A'
                    for field in programme_fields:
                        if row_dict.get(field):
                            programmes = row_dict.get(field)
                            break

                    result = {
                        'source': 'EU',
                        'name': name,
                        'type': 'Individual/Entity',
                        'programs': programmes,
                        'addresses': row_dict.get('Entity_remark', row_dict.get('entity_remark', 'N/A')),
                        'score': 'N/A',
                        'raw_data': {
                            'firstname': row_dict.get('Naal_firstname', row_dict.get('firstname', '')),
                            'lastname': row_dict.get('Naal_lastname', row_dict.get('lastname', '')),
                            'title': row_dict.get('Naal_title', row_dict.get('title', '')),
                            'function': row_dict.get('Naal_function', row_dict.get('function', '')),
                            'gender': row_dict.get('Naal_gender', row_dict.get('gender', '')),
                            'legal_ref': row_dict.get('Leba_numtitle', row_dict.get('legal_ref', '')),
                            'publication_date': row_dict.get('Leba_publication_date', row_dict.get('publication_date', '')),
                            'language': row_dict.get('Naal_language', row_dict.get('language', '')),
                            'match_details': row_dict.get('_match_details', []),
                            'all_fields': {k: v for k, v in row_dict.items() if v and k != '_match_details'}
                        }
                    }
                    results.append(result)

                print(f"🔍 EU: Processed {row_count} rows, found {len(results)} potential matches")

        except Exception as e:
            print(f"❌ Error searching EU database: {e}")
            import traceback
            traceback.print_exc()

        return results

    def download_un_html(self):
        """Download UN sanctions HTML file"""
        if os.path.exists(self.un_file):
            file_age = time.time() - os.path.getmtime(self.un_file)
            hours_old = file_age / 3600
            if hours_old < 4:
                print(f"📂 UN HTML file is recent ({hours_old:.1f} hours old). Using existing file.")
                return True
            else:
                print(f"📅 UN HTML file is {hours_old:.1f} hours old. Downloading updated version...")

        print("⬇️ Downloading UN sanctions HTML...")
        try:
            response = requests.get(self.un_url)
            if response.status_code == 200:
                with open(self.un_file, "wb") as f:
                    f.write(response.content)
                print(f"✅ UN HTML downloaded successfully")
                return True
            else:
                print(f"❌ Failed to download UN HTML. Status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error downloading UN HTML: {e}")
            return False

    def download_uk_html(self):
        """Download UK sanctions HTML file"""
        if os.path.exists(self.uk_file):
            file_age = time.time() - os.path.getmtime(self.uk_file)
            hours_old = file_age / 3600
            if hours_old < 4:
                print(f"📂 UK HTML file is recent ({hours_old:.1f} hours old). Using existing file.")
                return True
            else:
                print(f"📅 UK HTML file is {hours_old:.1f} hours old. Downloading updated version...")

        print("⬇️ Downloading UK sanctions HTML...")
        try:
            response = requests.get(self.uk_url)
            if response.status_code == 200:
                with open(self.uk_file, "wb") as f:
                    f.write(response.content)
                print(f"✅ UK HTML downloaded successfully")
                return True
            else:
                print(f"❌ Failed to download UK HTML. Status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error downloading UK HTML: {e}")
            return False

    def _search_html_source(self, file_path, query, source_label, default_program_label,
                            name_extraction=True, match_mode="tokens"):
        """
        Internal helper to scan an HTML file line-by-line and apply either:
        - tokens mode: require ≥2 distinct word matches, or
        - full_name mode: tolerant regex of the full name.
        Then attempt to extract name/program/info using your existing patterns.
        """
        print(f"🔍 Searching {source_label} database...")
        results = []

        if not os.path.exists(file_path):
            print(f"❌ {source_label}: file not found.")
            return results

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            query_words = self._prep_query_words(query)
            full_re = self._full_name_regex(query)

            matches = []
            for line_count, raw_line in enumerate(content.split("\n"), start=1):
                clean_line = raw_line.strip()
                if len(clean_line) < 10 or clean_line.startswith('<') or clean_line.startswith('//'):
                    continue

                if match_mode == "full_name":
                    if not full_re.search(clean_line):
                        continue
                    matched_words = query_words  # informative only
                else:
                    c = self._count_full_word_matches(clean_line, query_words)
                    if c < 2:
                        continue
                    matched_words = [w for w in query_words if re.search(r'\b' + re.escape(w) + r'\b', clean_line, re.IGNORECASE)]

                matches.append({
                    'line': clean_line,
                    'line_number': line_count,
                    'matched_words': matched_words,
                    'match_context': clean_line[:300]
                })

            # Process matches -> standardized format
            for i, match in enumerate(matches[:50]):  # safety cap
                match_text = match['line']
                extracted_name = 'N/A'

                # Try various patterns to extract names from HTML content
                name_patterns = [
                    r'name["\']?\s*:\s*["\']?([^"\'<>,]+)["\']?',
                    r'["\']name["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'>([A-Z][a-zA-Z\s]{5,50})<',
                    r'Individual[:\s]+([A-Z][a-zA-Z\s]{5,50})',
                    r'Entity[:\s]+([A-Z][a-zA-Z\s]{5,50})',
                ]

                if name_extraction:
                    for pattern in name_patterns:
                        name_match = re.search(pattern, match_text, re.IGNORECASE)
                        if name_match:
                            potential_name = name_match.group(1).strip()
                            if len(potential_name) > 3 and any(c.isalpha() for c in potential_name):
                                extracted_name = potential_name
                                break

                    if extracted_name == 'N/A':
                        # fallback: try to build name around context words (capitalized sequences)
                        words = match_text.split()
                        for j, word in enumerate(words):
                            word_clean = re.sub(r'[^\w\s]', '', word.lower())
                            if any(re.search(r'\b' + re.escape(qw) + r'\b', word_clean) for qw in query_words):
                                context_start = max(0, j - 3)
                                context_end = min(len(words), j + 4)
                                context_words = words[context_start:context_end]
                                name_candidates = []
                                for k, ctx_word in enumerate(context_words):
                                    if ctx_word and ctx_word[0].isupper() and len(ctx_word) > 2:
                                        name_candidates.append(ctx_word.strip('.,;:"()[]{}'))
                                if name_candidates:
                                    extracted_name = ' '.join(name_candidates[:3])
                                    break

                # Programs / committee information
                programs = default_program_label
                program_patterns = [
                    r'committee[:\s]+([^<>,\n]{10,100})',
                    r'program[me]?[:\s]+([^<>,\n]{10,100})',
                    r'sanction[s]?[:\s]+([^<>,\n]{10,100})',
                    r'resolution[:\s]+([^<>,\n]{10,50})'
                ]
                for pattern in program_patterns:
                    prog_match = re.search(pattern, match_text, re.IGNORECASE)
                    if prog_match:
                        programs = prog_match.group(1).strip()
                        break

                # Additional identifying information
                additional_info = 'N/A'
                info_patterns = [
                    r'address[es]?[:\s]+([^<>\n]{10,200})',
                    r'identifier[s]?[:\s]+([^<>\n]{10,100})',
                    r'alias[es]?[:\s]+([^<>\n]{10,100})',
                    r'born[:\s]+([^<>\n]{5,50})'
                ]
                for pattern in info_patterns:
                    info_match = re.search(pattern, match_text, re.IGNORECASE)
                    if info_match:
                        additional_info = info_match.group(1).strip()
                        break

                result = {
                    'source': source_label,
                    'name': extracted_name,
                    'type': f'{source_label} Sanctions List Entry' if source_label in ('UK', 'UN') else 'Consolidated List Entry',
                    'programs': programs,
                    'addresses': additional_info,
                    'score': 'N/A',
                    'raw_data': {
                        'match_text': match['match_context'],
                        'matched_words': match['matched_words'],
                        'line_number': match['line_number'],
                        'full_line': match['line'][:500],
                        'extraction_method': 'Full-name regex' if match_mode == 'full_name' else 'Enhanced token matching (≥2 tokens)'
                    }
                }
                results.append(result)

            print(f"✅ {source_label}: Found {len(results)} matches")

        except Exception as e:
            print(f"❌ Error searching {source_label} database: {e}")
            import traceback
            traceback.print_exc()

        return results

    def search_un(self, query, match_mode="tokens"):
        if not self.download_un_html():
            return []
        return self._search_html_source(
            file_path=self.un_file,
            query=query,
            source_label='UN',
            default_program_label='UN Security Council',
            name_extraction=True,
            match_mode=match_mode
        )

    def search_uk(self, query, match_mode="tokens"):
        if not self.download_uk_html():
            return []
        return self._search_html_source(
            file_path=self.uk_file,
            query=query,
            source_label='UK',
            default_program_label='UK Sanctions',
            name_extraction=True,
            match_mode=match_mode
        )

    # ---------------------------
    # Aggregators
    # ---------------------------
    def search_all_sources(self, query, client_id, owner_type, recipient_id, match_mode="tokens", only_return=False):
        """Search all sources; optional full-name mode; optionally skip side-effects and just return."""
        print(f"🌍 Searching all sanctions databases for: '{query}' (mode={match_mode})")
        print("=" * 60)

        all_results = []
        all_results.extend(self.search_ofac(query, client_id, recipient_id))
        all_results.extend(self.search_eu(query, match_mode=match_mode))
        all_results.extend(self.search_uk(query, match_mode=match_mode))
        all_results.extend(self.search_un(query, match_mode=match_mode))
        
        print("Results compiled from all sources:", all_results)
        print("=" * 60)
        print(f"🎯 Total results across all databases: {len(all_results)}")
        return all_results

    def search_full_name_only(self, full_name, client_id=None, owner_type=None, recipient_id=None, min_score_threshold=None):
        """
        Full-name search across OFAC/EU/UK/UN and return only if matches exist.
        - No report generation or Mambu updates here.
        - Uses exact-ish full-name matching for EU/UK/UN; OFAC unchanged.
        """
        if min_score_threshold is not None:
            self.min_score_threshold = min_score_threshold

        print(f"🌍 Full-name screening for: '{full_name}'")
        all_results = []
        all_results.extend(self.search_ofac(full_name, client_id, recipient_id))
        all_results.extend(self.search_eu(full_name, match_mode="full_name"))
        all_results.extend(self.search_uk(full_name, match_mode="full_name"))
        all_results.extend(self.search_un(full_name, match_mode="full_name"))
        print(f"🎯 Full-name totals: {len(all_results)}")
        return all_results

    # ---------------------------
    # Reporting & Mambu upload
    # ---------------------------
    def create_unified_report(self, all_results, query, client_id, owner_type):
        print("CLIENTID", client_id)
        """Generate a unified report with results from all sources - for both matches and no matches"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"unified_sanctions_report_{query.replace(' ', '_')}_{timestamp}.txt"
        filepath = os.path.join(settings.MEDIA_ROOT, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as report_file:
                # Header
                report_file.write("=" * 80 + "\n")
                report_file.write("UNIFIED SANCTIONS SEARCH REPORT \n")
                report_file.write("=" * 80 + "\n")
                report_file.write(f"Search Query: {query}\n")
                report_file.write(f"Client/Loan ID: {client_id}\n")
                report_file.write(f"Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                report_file.write(f"Total Results: {len(all_results)}\n")
                report_file.write(f"Sources Searched: OFAC, EU, UN, UK\n")
                report_file.write("=" * 80 + "\n\n")

                sources = {'OFAC': [], 'EU': [], 'UN': [], 'UK': []}
                for result in all_results:
                    source = result['source']
                    if source in sources:
                        sources[source].append(result)

                if len(all_results) > 0:
                    # Matches found
                    report_file.write("⚠️  SANCTIONS MATCHES FOUND ⚠️\n")
                    report_file.write("=" * 50 + "\n")
                    report_file.write("COMPLIANCE REVIEW REQUIRED\n\n")

                    for source, results in sources.items():
                        report_file.write(f"{source} SANCTIONS DATABASE RESULTS\n")
                        report_file.write("=" * 50 + "\n")
                        if len(results) > 0:
                            report_file.write(f"Results found: {len(results)}\n\n")
                            for i, result in enumerate(results, 1):
                                report_file.write(f"RESULT #{i}\n")
                                report_file.write("-" * 40 + "\n")
                                report_file.write(f"Source: {result['source']}\n")
                                report_file.write(f"Name: {result['name']}\n")
                                report_file.write(f"Type: {result['type']}\n")
                                report_file.write(f"Programs: {result['programs']}\n")
                                report_file.write(f"Additional Info: {result['addresses']}\n")
                                report_file.write(f"Match Score: {result['score']}\n")
                                if source == 'EU' and 'raw_data' in result:
                                    raw = result['raw_data']
                                    report_file.write(f"First Name: {raw.get('firstname', 'N/A')}\n")
                                    report_file.write(f"Last Name: {raw.get('lastname', 'N/A')}\n")
                                    report_file.write(f"Title: {raw.get('title', 'N/A')}\n")
                                    report_file.write(f"Function: {raw.get('function', 'N/A')}\n")
                                elif source == 'UN' and 'raw_data' in result:
                                    report_file.write(f"Match Text: {result['raw_data'].get('match_text', 'N/A')}\n")
                                report_file.write("\n" + "=" * 40 + "\n\n")
                        else:
                            report_file.write("Results found: 0\n")
                            report_file.write("No matches identified in this database.\n\n")
                        report_file.write("\n")

                    # Summary
                    report_file.write("SEARCH SUMMARY\n")
                    report_file.write("=" * 50 + "\n")
                    for source in ['OFAC', 'EU', 'UN', 'UK']:
                        count = len(sources[source])
                        report_file.write(f"{source}: {count} matches\n" if count > 0 else f"{source}: NO MATCHES\n")

                    report_file.write("\nRECOMMENDATION: COMPLIANCE REVIEW REQUIRED\n")
                    report_file.write("This client has potential sanctions matches and requires manual review.\n")
                else:
                    # No matches: keep minimal header only (as in your original code it did pass)
                    pass

            print(f"📄 Unified report generated: {filepath}")
            return filepath

        except Exception as e:
            print(f"❌ Error creating unified report: {e}")
            return None


    def send_email_notification(self, query, client_id, report_filename):
        """Send email notification about sanctions screening results - only when matches are found"""
        try:
            matches_found = False
            if os.path.exists(report_filename):
                with open(report_filename, 'r') as f:
                    content = f.read()
                    if "SANCTIONS MATCHES FOUND" in content:
                        matches_found = True

            if not matches_found:
                print(f"ℹ️ No sanctions matches found - email notification skipped (report still attached)")
                return

            CLIENT_SECRET_FILE = gmail_credentials_compliance

            email_subject = f"🚨SANCTIONS ALERT: Matches found for '{query}' (Client: {client_id})"
            email_body = f"""\
                <html>
                <head></head>
                <body>
                <h3 style="color: red;">⚠️ SANCTIONS SCREENING ALERT ⚠️</h3>
                <p><strong>Client:</strong> {query} (ID: {client_id})</p>
                <p><strong>Status:</strong> POTENTIAL SANCTIONS MATCHES FOUND</p>
                <p><strong>Action Required:</strong> IMMEDIATE COMPLIANCE REVIEW</p>
                <p>Please find the attached detailed sanctions report for your review.</p>
                <p>This client should NOT be onboarded until compliance review is complete.</p>
                <hr>
                <p><em>This is an automated notification from the sanctions screening system.</em></p>
                </body>
                </html>
                """

            recipient_email = self.compliance_email

            mimeMessage = MIMEMultipart()
            mimeMessage['to'] = recipient_email
            mimeMessage['cc'] = self.credit_email
            mimeMessage['subject'] = email_subject
            mimeMessage.attach(MIMEText(email_body, 'html'))

            if os.path.exists(report_filename):
                with open(report_filename, 'rb') as f:
                    attachment_data = f.read()
                part = MIMEApplication(attachment_data, _subtype='txt')
                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(report_filename))
                mimeMessage.attach(part)

            raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()
            _ = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
            print(f"📧 Sanctions alert email sent to {recipient_email}")

        except HttpError as err:
            print(f"❌ Failed to send email: {err}")
        except Exception as e:
            print(f"❌ Error sending email notification: {e}")

    # ---------------------------
    # Mambu-driven flows (unchanged, with small touch-ups)
    # ---------------------------
    def screen_client(self, client_id, owner_type):
        """Screen a specific Mambu client by ID"""
        print(f"🔍 Screening Mambu client: {client_id}")

        try:
            client_url = f"{self.mambu_base_url}/api/clients/{client_id}"
            headers = {
                'Accept': 'application/vnd.mambu.v2+json',
                'Authorization': f'Basic {self.mambu_api_key}'
            }
            response = requests.get(client_url, headers=headers, timeout=30)

            if response.status_code == 200:
                client_data = response.json()
                first_name = client_data.get('firstName', '')
                last_name = client_data.get('lastName', '')
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    print(f"❌ Could not extract client name from Mambu data")
                    return

                print(f"👤 Client name: {full_name}")

                # Full-name search (return-only)
                all_results = self.search_full_name_only(full_name, client_id=client_id, owner_type=owner_type)

                if all_results:
                    print(f"\n⚠️ SANCTIONS ALERT: Found {len(all_results)} matches for client {client_id}")
                    sources_summary = {}
                    for result in all_results:
                        source = result['source']
                        sources_summary[source] = sources_summary.get(source, 0) + 1

                    print("\nResults breakdown:")
                    for source, count in sources_summary.items():
                        print(f"  • {source}: {count} matches")

                    # If you want side-effects, call the aggregator without only_return
                    report_file = self.create_unified_report(all_results, full_name, client_id, owner_type)
                    if report_file:
                        mambu_success = self.upload_to_mambu(report_file, client_id, full_name, owner_type)
                        if mambu_success:
                            print(f"\n🚨 COMPLIANCE ACTION REQUIRED: Report attached to client {client_id}")
                            print(f"📧 Recommend notifying: {self.compliance_email}")
                        else:
                            print(f"\n⚠️ Report created but failed to attach to client {client_id}")
                            print(f"📧 Recommend notifying: {self.compliance_email}")
                else:
                    print(f"\n✅ No sanctions matches found for client {client_id}")

            else:
                print(f"❌ Failed to fetch client data from Mambu. Status: {response.status_code}")
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"❌ Error screening client {client_id}: {e}")

    def run(self, client_id=None, owner_type=None, recipient_id=None):
        """Run the sanctions search bot"""
        print("🌍 Welcome to the Sanctions Search Bot!")
        print("This bot searches across OFAC, EU, and UN sanctions databases simultaneously.")
        print("=" * 70)
        
        # Get search query from user
        query = input("📝 Please enter the name or term to search for: ").strip()
        
        if not query:
            print("❌ Please provide a valid search term.")
            return
            
        # Get client ID if not provided
        if not client_id:
            client_input = input("📝 Enter Mambu Client ID (optional, press Enter to skip): ").strip()
            if client_input:
                client_id = client_input
        
        print(f"\n🚀 Starting comprehensive search for: '{query}'")
        print("This may take a few moments as we search multiple databases...\n")
        
        # Search all sources
        all_results = self.search_all_sources(query, client_id, owner_type, recipient_id)

        # Display summary
        if all_results:
            print(f"\n✅ Search completed! Found {len(all_results)} total matches across all databases.")
            
            # Show brief summary
            sources_summary = {}
            for result in all_results:
                source = result['source']
                sources_summary[source] = sources_summary.get(source, 0) + 1
            
            print("\nResults breakdown:")
            for source, count in sources_summary.items():
                print(f"  • {source}: {count} matches")
            
            # Generate unified report (now consistently using owner_type)
            report_file = self.create_unified_report(all_results, query, client_id, owner_type)

        else:
            print(f"\n❌ No matches found for '{query}' across all databases.")
            print("No report generated as no matches were found.")
        
        print("\n🎉 Thank you for using the Unified Sanctions Search Bot!")
        print("Your search has been completed and documented.")
    

    def screen_from_api(self, request_data):
        """Screen based on API request parameters"""
        try:
            query = request_data.get('query', '').strip()
            include_report = request_data.get('include_report', True)
            min_score_threshold = request_data.get('min_score_threshold', 80)
            owner_key = request_data.get('owner_key')
            client_id = request_data.get('client_id')
            owner_type = request_data.get('owner_type')
            recipient_id = request_data.get('recipient_id')
            match_mode = request_data.get('match_mode', 'full_name')  # default to full-name for API

            if not query:
                return {
                    'success': False,
                    'error': 'Query parameter is required',
                    'matches_found': 0,
                    'report_created': False
                }

            print(f"🌍 API Sanctions Screening Request")
            print(f"Query: {query}")
            print(f"Owner Key: {owner_key}")
            print(f"Owner Type: {owner_type}")
            print(f"Min Score Threshold: {min_score_threshold}")
            print(f"Include Report: {include_report}")
            print(f"Match Mode: {match_mode}")
            print("=" * 60)

            self.min_score_threshold = min_score_threshold

            all_results = self.search_all_sources(
                query=query,
                client_id=client_id,
                owner_type=owner_type,
                recipient_id=recipient_id,
                match_mode=match_mode,
                only_return=True  # API first: no side-effects until we decide below
            )

            # Filter by score threshold if applicable
            filtered_results = []
            for result in all_results:
                score = result.get('score')
                if score == 'N/A' or (isinstance(score, (int, float)) and score >= min_score_threshold):
                    filtered_results.append(result)

            response = {
                'success': True,
                'query': query,
                'matches_found': len(filtered_results),
                'total_unfiltered_matches': len(all_results),
                'min_score_threshold': min_score_threshold,
                'owner_key': owner_key,
                'report_created': False,
                'report_filename': None,
                'mambu_upload_success': False,
                'results': []
            }

            if filtered_results:
                print(f"\n⚠️ SANCTIONS ALERT: Found {len(filtered_results)} matches above threshold {min_score_threshold}")
                sources_summary = {}
                for result in filtered_results:
                    source = result['source']
                    sources_summary[source] = sources_summary.get(source, 0) + 1
                    response['results'].append({
                        'source': result['source'],
                        'name': result['name'],
                        'type': result['type'],
                        'programs': result['programs'],
                        'score': result['score'],
                        'match_details': result.get('addresses', 'N/A')
                    })
                response['sources_summary'] = sources_summary
            else:
                print(f"✅ No sanctions matches found above threshold {min_score_threshold}")
                if all_results:
                    print(f"ℹ️ {len(all_results)} matches found below threshold were filtered out")
                else:
                    print("ℹ️ No matches found in any database")

            # Create and upload report if requested
            if include_report:
                report_file = self.create_unified_report(filtered_results, query, client_id, owner_type)
                if report_file:
                    response['report_created'] = True
                    response['report_filename'] = report_file
                    if owner_key:
                        mambu_success = self.upload_to_mambu(report_file, owner_key, query, owner_type)
                        response['mambu_upload_success'] = mambu_success

            return response

        except Exception as e:
            print(f"❌ Error in API sanctions screening: {e}")
            return {
                'success': False,
                'error': str(e),
                'matches_found': 0,
                'report_created': False
            }


if __name__ == "__main__":
    bot = UnifiedSanctionsBot()
    # CLI defaults to full-name mode, and only returns/prints matches (no side-effects unless you opt-in in the prompts).
    bot.run()