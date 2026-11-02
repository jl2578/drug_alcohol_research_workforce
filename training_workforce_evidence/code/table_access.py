"""Readable, hash-checked table exports and an offline catalog (standard library)."""
import csv
import hashlib
import html
import io
import json
import re
import shutil
import zipfile
from pathlib import Path


def select(rows, expression):
    """Evaluate only the documented equality/set grammar, never Python code."""
    terms = []
    for term in expression.split(" and "):
        match = re.fullmatch(r"(\w+) = ([\w.-]+)", term)
        if match:
            terms.append((match[1], {match[2]}))
            continue
        match = re.fullmatch(r"(\w+) in \{([^{}]+)\}", term)
        if not match:
            raise ValueError("Unsupported table filter: " + expression)
        terms.append((match[1], {v.strip() for v in match[2].split(",")}))
    return [row for row in rows if all(row[key] in values for key, values in terms)]


def content(core, entry, entries, stacks, active=()):
    key = entry["table"]
    if key in active:
        raise ValueError("Cyclic table view: " + key)
    storage = entry["storage"]
    if storage == "stacked":
        value = core.table_bytes(entry, stacks[key])
    elif storage == "whole":
        value = (core.PACKAGE / entry["file"]).read_bytes()
    elif storage in {"alias", "view"}:
        spec = json.loads(entry["filter"])
        original = content(core, entries[spec["source_table"]], entries, stacks, active + (key,))
        if storage == "alias":
            value = original
        else:
            reader = csv.DictReader(io.StringIO(original.decode("utf-8-sig"), newline=""))
            rows = list(reader)
            if spec.get("where"):
                if isinstance(spec["where"], dict):
                    rows = [r for r in rows if all(r[k] in values for k, values in spec["where"].items())]
                else:
                    rows = select(rows, spec["where"])
            if spec.get("group_by_first_seen"):
                groups = {}
                for row in rows:
                    group = tuple(row[k] for k in spec["group_by_first_seen"])
                    groups.setdefault(group, []).append(row)
                rows = [row for group in groups.values() for row in group]
            columns = spec["columns"]
            source_columns = spec.get("source_columns", columns)
            value = core.table_bytes(entry, [columns] + [[r[c] for c in source_columns] for r in rows])
    elif storage == "filtered":
        with (core.PACKAGE / entry["file"]).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            rows = select(list(reader), entry["filter"])
        value = core.table_bytes(entry, [columns] + [[r[c] for c in columns] for r in rows])
    else:
        with zipfile.ZipFile(core.PACKAGE / entry["file"]) as archive:
            value = archive.read(key)
    if entry.get("sha256") and hashlib.sha256(value).hexdigest() != entry["sha256"]:
        raise ValueError("Table hash mismatch: " + key)
    if key.endswith(".json"):
        json.loads(value)
    else:
        parsed = list(csv.reader(io.StringIO(value.decode("utf-8-sig"), newline="")))
        if len(parsed) - 1 != int(entry["rows"]) or len(parsed[0]) != int(entry["columns"]):
            raise ValueError("Table shape mismatch: " + key)
    return value


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def topic(entry):
    name = entry["table"].removeprefix("DISPLAY_")
    return next((f"DEP{i}" for i in range(1, 5) if name.startswith(f"DEP{i}")), "NIH")


def anchor(key):
    return "table-" + re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def rich(value):
    """Render limited source formatting without executing stored markup."""
    value = html.escape(value, quote=True)
    value = re.sub(r"&lt;br\s*/?&gt;", "<br>", value, flags=re.I)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    # All source captions are local scientific prose. Links retain safe schemes.
    value = re.sub(r"\[([^\]]+)\]\(((?:https?://|[A-Za-z0-9_.#/])[A-Za-z0-9_./:#?%=&;~+,-]*)\)", r'<a href="\2">\1</a>', value)
    return value


def paragraphs(value):
    return "".join("<p>" + rich(part.strip()) + "</p>" for part in re.split(r"\n\s*\n", value) if part.strip())


def source_links(keys, entries):
    return " · ".join(f'<a href="#{anchor(key)}">{html.escape(entries[key]["title"])}</a>' if key in entries else html.escape(key) for key in keys)


def catalog(core, output, exported=None):
    """Build the anchored display, figure and source-table catalog from metadata."""
    esc = html.escape
    dictionary = read_csv(core.PACKAGE / "DATA_DICTIONARY.csv")
    displays = read_csv(core.PACKAGE / "DISPLAY_MAP.csv")
    metadata_path = core.DATA / "catalog_displays.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {"tables": [], "figures": []}
    entries = {entry["table"]: entry for entry in core.index()}
    stacks = core.load_stacks(entries.values())
    snapshot_ids = {item["snapshot_table"] for item in metadata["tables"]}
    groups = {f"DEP{i}": [] for i in range(1, 5)}
    groups["NIH"] = []
    figure_cards = []

    for item in metadata["tables"]:
        key = item["snapshot_table"]
        value = content(core, entries[key], entries, stacks)
        rows = list(csv.reader(io.StringIO(value.decode("utf-8-sig"), newline="")))
        location = exported[key] if exported else item["csv_file"]
        table_html = "<div class=scroll><table><thead><tr>" + "".join("<th>" + rich(cell) + "</th>" for cell in rows[0]) + "</tr></thead><tbody>"
        table_html += "".join("<tr>" + "".join("<td>" + rich(cell) + "</td>" for cell in row) + "</tr>" for row in rows[1:]) + "</tbody></table></div>"
        note_html = paragraphs(item.get("notes", ""))
        search = " ".join((item["display"], item["title"], item.get("former_label", ""), " ".join(item["source_tables"]))).lower()
        card = f'''<article id="{item['id']}" data-search="{esc(search, quote=True)}"><span id="{anchor(key)}"></span><h3>{esc(item['display'])}. {esc(item['title'])}</h3>
<p><a href="{esc(location, quote=True)}">Download saved display CSV</a> · {len(rows)-1} displayed rows</p>
{paragraphs(item.get('preamble', ''))}<details class="display"><summary>Read table and notes</summary>{table_html}{note_html}</details>
<p class="limits">{esc(item['source_limit'])}</p>
<p><b>Underlying sources:</b> {source_links(item['source_tables'], entries) or 'No separate underlying aggregate table supplied; see the limitation above.'}</p>
<details><summary>Original verification scope</summary><p>{esc(item.get('original_check', '') or 'No independent reconstruction claimed.')} {esc(item.get('original_map_note', ''))}</p><p>Snapshot checks establish exact transcription and file integrity; they do not reconstruct withheld records or upgrade the original analysis checks.</p></details></article>'''
        groups[item["id"].split("-")[0].upper()].append(card)

    for item in metadata["figures"]:
        links = " · ".join(f'<a href="{esc(name, quote=True)}">Open {esc(name.rsplit("/", 1)[-1])}</a>' for name in item["files"])
        preview = next((name for name in item["files"] if name.endswith(".svg")), None)
        preview_html = f'<a href="{esc(preview, quote=True)}"><img loading="lazy" src="{esc(preview, quote=True)}" alt="{esc(item.get("alt", item["title"]), quote=True)}"></a>' if preview else ""
        captions = "".join(paragraphs(caption) for caption in item["captions"])
        search = " ".join((item["display"], item["title"], "figure", item.get("note", ""))).lower()
        figure_cards.append(f'''<article id="{item['id']}" data-search="{esc(search, quote=True)}"><h3>{esc(item['display'])}. {esc(item['title'])}</h3><p>{links}</p>{preview_html}<details><summary>Caption and interpretation</summary>{captions}{paragraphs(item.get('alt', ''))}</details>{paragraphs(item.get('note', ''))}<p><b>Source tables:</b> {source_links(item['source_tables'], entries)}</p></article>''')

    for key, entry in entries.items():
        if key in snapshot_ids:
            continue
        definitions = [row for row in dictionary if row["table"] == key]
        if not definitions and entry["storage"] == "filtered":
            source = next(e for e in entries.values() if e["file"] == entry["file"] and e["storage"] == "whole")
            definitions = [row for row in dictionary if row["table"] == source["table"]]
        linked = [row for row in displays if key in [part.strip() for part in row["table"].split(";")]]
        location = exported[key] if exported else entry["file"]
        filter_label = entry["filter"]
        if entry["storage"] in {"alias", "view"}:
            filter_label = "Reconstructed from " + json.loads(entry["filter"])["source_table"]
        definition_html = "".join("<tr>" + "".join(f"<td>{rich(row[k])}</td>" for k in ("column", "definition", "units_or_values", "missing")) + "</tr>" for row in definitions)
        display_parts = []
        for display in linked:
            label = esc(display["display"])
            where = display["where"]
            if where.startswith("TABLES.html#"):
                label = f'<a href="#{esc(where.split("#", 1)[1], quote=True)}">{label}</a>'
            elif not exported and where:
                where = "supplement/Supplement_S1_S4.pdf" if where == "supplement" else where.split(";")[0].strip()
                label = f'<a href="{esc(where, quote=True)}">{label}</a>'
            display_parts.append(f'<li>{label} — {esc(display["title"])}</li>')
        search = " ".join([key, entry["title"], entry["description"], entry["backs_displays"], topic(entry)]).lower()
        search += " " + " ".join(" ".join(row[k] for k in ("display", "title", "former_label")) for row in linked).lower()
        command = f'python code/verify_all.py export "{key}" --output table.' + ("json" if key.endswith(".json") else "csv")
        card = f'''<article id="{anchor(key)}" data-search="{esc(search, quote=True)}"><h3>{esc(entry['title'])}</h3>
<p class="id">{esc(key)}</p><p>{esc(entry['description'])}</p><p>{esc(entry['rows'])} rows · {esc(entry['columns'])} columns · Check: {esc(entry['check'])}</p>
<p><a href="{esc(location, quote=True)}">{'Open table' if exported else 'Source file'}</a> · {esc(entry['storage'])}{' · '+esc(filter_label) if filter_label else ''}</p>
{'' if exported else '<details><summary>Export an ordinary table</summary><pre>'+esc(command)+'</pre></details>'}
<p>{esc(entry['rights_scope'])}</p><details><summary>Displays and column definitions</summary><ul>{''.join(display_parts) or '<li>Supporting evidence; no direct publication display.</li>'}</ul>
{'<div class=scroll><table><thead><tr><th>Column</th><th>Definition</th><th>Units/values</th><th>Missing</th></tr></thead><tbody>'+definition_html+'</tbody></table></div>' if definitions else '<p>Retain the supplied header and source-note fields; the table-specific definitions are recorded in DATA_DICTIONARY.csv where available.</p>'}</details></article>'''
        groups[topic(entry)].append(card)

    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Supplement evidence — tables and figures</title>
<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1180px;margin:36px auto;padding:0 24px;color:#182d35;background:#fafcfb}h1{font-size:2rem}h2{margin-top:2em}h3{font-size:1.12rem}a{color:#075d85}input{font:inherit;padding:12px;width:95%;border:1px solid #738b90;border-radius:6px}article{background:white;border:1px solid #cbd7d9;border-radius:8px;padding:20px;margin:16px 0;scroll-margin-top:16px}article:target{border:2px solid #075d85}article[hidden]{display:none}.id,pre,code{font-family:monospace;font-size:13px;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#edf3f3;padding:12px}summary{cursor:pointer;font-weight:600;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #cbd7d9;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}p{margin:.6em 0}.scroll{overflow-x:auto}.limits{font-size:14px;color:#40565e}img{max-width:100%;max-height:540px}nav{display:flex;flex-wrap:wrap;gap:16px;margin:1em 0}details>p:last-child{margin-bottom:1em}</style>
<h1>Supplement evidence: tables and figures</h1>'''
    page += '<p>Find a publication display, inspect its saved table or caption, and follow its underlying data. The 50 extended tables preserve every printed cell as an ordinary CSV. Their saved precision and unavailable markers remain unchanged.</p>'
    page += '<p><a href="DATA_DICTIONARY.csv">Full dictionary</a> · <a href="DATA_AVAILABILITY.md">Reuse and disclosure limits</a>'
    if not exported:
        page += ' · <a href="README.md">Package guide</a> · <a href="REPRODUCTION.md">Checks and limits</a> · <a href="supplement/Supplement_S1_S4.pdf">S1–S4 supplement</a>'
    page += '</p><nav><a href="#figures">Figures</a><a href="#dep1">Corpus and measurement</a><a href="#dep2">Research content</a><a href="#dep3">NIH connections and funding</a><a href="#dep4">Employment and RC-RMI</a><a href="#nih">Funding reconstruction</a></nav>'
    if not exported:
        page += '<details><summary>Export all ordinary data tables</summary><pre>python code/verify_all.py export-tables --output ../readable-tables</pre></details>'
    page += '<p>A named check covers only its documented arithmetic or model route. A saved display transcription preserves already reported information; it does not independently reproduce withheld records, judgments or private fits. Filtered source tables are views of shared data, not additional observations.</p><label for="search">Find a table, figure or display</label><input id="search" type="search" placeholder="For example: DEP3-E26, opioid, or S4.15"><p id="count" role="status"></p><h2 id="figures">Figure gallery</h2>'
    page += "\n".join(figure_cards)
    labels = {"DEP1": "Corpus and measurement", "DEP2": "Research content", "DEP3": "NIH connections and funding", "DEP4": "Employment and RC-RMI", "NIH": "Funding reconstruction"}
    for group, cards in groups.items():
        page += f'<section><h2 id="{group.lower()}">{esc(labels[group])}</h2>' + "\n".join(cards) + '</section>'
    page += r'''<script>const input=document.getElementById('search'),cards=[...document.querySelectorAll('article')];function filter(){const words=input.value.toLowerCase().trim().split(/\s+/);let n=0;for(const card of cards){card.hidden=!words.every(w=>card.dataset.search.includes(w));if(!card.hidden)n++;}document.getElementById('count').textContent=n+' of '+cards.length+' entries';}function reveal(){if(!location.hash)return;const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(!target)return;const card=target.closest('article');if(card){input.value='';filter();card.querySelectorAll('details.display').forEach(d=>d.open=true);}requestAnimationFrame(()=>target.scrollIntoView());}input.addEventListener('input',filter);window.addEventListener('hashchange',reveal);filter();reveal();</script></html>'''
    output.write_text(page, encoding="utf-8", newline="\n")


def export_tables(core, output):
    output = output.resolve()
    if output == core.PACKAGE or core.PACKAGE in output.parents:
        raise SystemExit("--output must be outside this package")
    if output.exists() and any(output.iterdir()):
        raise SystemExit("--output must be a new or empty folder")
    entries = {e["table"]: e for e in core.index()}
    stacks = core.load_stacks(entries.values())
    output.mkdir(parents=True, exist_ok=True)
    paths, rows = {}, []
    for number, entry in enumerate(entries.values(), 1):
        key = entry["table"]
        suffix = ".json" if key.endswith(".json") else ".csv"
        slug = re.sub(r"[^a-z0-9]+", "_", entry["title"].lower()).strip("_")[:55]
        relative = f"{topic(entry)}/{number:03}_{slug}{suffix}"
        value = content(core, entry, entries, stacks)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        paths[key] = relative
        rows.append({"table": key, "title": entry["title"], "file": relative, "rows": entry["rows"], "columns": entry["columns"], "sha256": hashlib.sha256(value).hexdigest(), "backs_displays": entry["backs_displays"], "check": entry["check"], "rights_scope": entry["rights_scope"]})
    with (output / "INDEX.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for name in ("DATA_DICTIONARY.csv", "LICENSE-MIT.txt", "LICENSE-CC-BY-4.0.txt"):
        shutil.copyfile(core.PACKAGE / name, output / name)
    notice = (core.PACKAGE / "DATA_AVAILABILITY.md").read_text(encoding="utf-8")
    notice = notice.replace("[data/TABLE_INDEX.csv](data/TABLE_INDEX.csv)", "[INDEX.csv](INDEX.csv)").replace("[MANIFEST.csv](MANIFEST.csv)", "[INDEX.csv](INDEX.csv)")
    (output / "DATA_AVAILABILITY.md").write_text(notice, encoding="utf-8")
    # Preserve the funding provenance archive cited in the reuse notice.
    (output / "data").mkdir(exist_ok=True)
    shutil.copyfile(core.DATA / "nih_funding_rebuild.zip", output / "data/nih_funding_rebuild.zip")
    # Keep the gallery usable in the standalone convenience export.
    if (core.PACKAGE / "figures").exists():
        shutil.copytree(core.PACKAGE / "figures", output / "figures")
    catalog(core, output / "TABLES.html", paths)
    (output / "README.txt").write_text("Open TABLES.html to find the ordinary tables. INDEX.csv identifies their hashes and reuse scope. This is a convenience export, not a replacement release package. Data/source provenance and the full dictionary are retained. Numeric strings and missing values are preserved; filtered views contain only selected rows. Reproduction code and the supplement remain in the source package.\n", encoding="utf-8")
    print(f"Exported {len(rows)} entries; open {output / 'TABLES.html'}")
