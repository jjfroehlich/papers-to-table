from __future__ import annotations

from jinja2 import DictLoader, Environment, select_autoescape


_COMPONENTS_TEMPLATE = """
{% macro badge(text, tone='neutral') -%}
<span class="badge badge-{{ tone }}">{{ text }}</span>
{%- endmacro %}

{% macro metric_card(card) -%}
<article class="metric-card card {{ card['class_name'] or '' }}">
  <div class="eyebrow">{{ card['label'] }}</div>
  <div class="metric-value">{{ card['value'] }}</div>
  {% if card['badges'] %}
  <div class="chip-row">
    {% for item in card['badges'] %}{{ badge(item['text'], item['tone']) }}{% endfor %}
  </div>
  {% endif %}
  {% if card['note'] %}<p class="note">{{ card['note'] }}</p>{% endif %}
</article>
{%- endmacro %}

{% macro bullet_card(section) -%}
<article class="card">
  <h3>{{ section['title'] }}</h3>
  {% if section['lead'] %}<p class="lead">{{ section['lead'] }}</p>{% endif %}
  {% if section['badges'] %}
  <div class="chip-row section-chips">
    {% for item in section['badges'] %}{{ badge(item['text'], item['tone']) }}{% endfor %}
  </div>
  {% endif %}
  <ul class="bullet-list">
    {% for item in section['items'] %}<li>{{ item }}</li>{% endfor %}
  </ul>
</article>
{%- endmacro %}

{% macro table_card(table) -%}
<section class="card table-card">
  <div class="section-head">
    <div>
      <h2>{{ table.title }}</h2>
      {% if table.subtitle %}<p class="section-subtitle">{{ table.subtitle }}</p>{% endif %}
    </div>
    {% if table.links %}
    <div class="link-row">
      {% for link in table.links %}<a href="{{ link.href }}">{{ link.label }}</a>{% endfor %}
    </div>
    {% endif %}
  </div>
  <div class="table-wrap">
    <table data-sortable="true">
      <thead>
        <tr>
          {% for column in table.columns %}
          <th class="align-{{ column.align or 'left' }}" data-sort="{{ column.sort or 'string' }}">{{ column.label }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in table.rows %}
        <tr>
          {% for idx in range(table.columns|length) %}
          {% set cell = row.cells[idx] %}
          {% set column = table.columns[idx] %}
          <td class="align-{{ column.align or 'left' }}" data-sort-value="{{ cell.sort }}">
            {% if cell.badge %}{{ badge(cell.badge, cell.tone) }}{% endif %}
            <div class="cell-text {{ 'monospace' if cell.monospace else '' }}">{{ cell.text }}</div>
            {% if cell.subtext %}<div class="cell-subtext">{{ cell.subtext }}</div>{% endif %}
            {% if cell.details %}<details><summary>details</summary><div class="cell-details">{{ cell.details }}</div></details>{% endif %}
          </td>
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
{%- endmacro %}

{% macro plot_card(plot) -%}
<article class="card plot-card {{ 'plot-hero' if plot.hero else '' }}">
  <div class="plot-head">
    <div>
      <h3>{{ plot.title }}</h3>
      {% if plot.subtitle %}<p class="section-subtitle">{{ plot.subtitle }}</p>{% endif %}
    </div>
    <div class="link-row">
      {% if plot.csv_href %}<a href="{{ plot.csv_href }}">CSV</a>{% endif %}
      {% if plot.png_href %}<a href="{{ plot.png_href }}">PNG</a>{% endif %}
      {% if plot.pdf_href %}<a href="{{ plot.pdf_href }}">PDF</a>{% endif %}
    </div>
  </div>
  {% if plot.image_data_uri %}
  <img src="{{ plot.image_data_uri }}" alt="{{ plot.title }}">
  {% else %}
  <div class="empty-state">Plot image not generated.</div>
  {% endif %}
  <div class="guidance-grid">
    <div>
      <div class="eyebrow">What This Shows</div>
      <p>{{ plot.guidance.what }}</p>
    </div>
    <div>
      <div class="eyebrow">How To Read It</div>
      <p>{{ plot.guidance.how }}</p>
    </div>
    <div>
      <div class="eyebrow">What To Watch For</div>
      <p>{{ plot.guidance.watch }}</p>
    </div>
  </div>
</article>
{%- endmacro %}

{% macro stage_card(stage) -%}
<article class="card stage-card">
  <div class="stage-topline">
    <div>
      <div class="eyebrow">{{ stage['stage_type'] }}</div>
      <h3>{{ stage['stage_name'] }}</h3>
    </div>
    <div class="chip-row">
      {% for chip in stage['badges'] %}{{ badge(chip['text'], chip['tone']) }}{% endfor %}
    </div>
  </div>
  <p class="lead">{{ stage['summary'] }}</p>
  <div class="metric-mini-grid">
    {% for item in stage['metrics'] %}
    <div>
      <div class="eyebrow">{{ item['label'] }}</div>
      <div class="mini-value">{{ item['value'] }}</div>
    </div>
    {% endfor %}
  </div>
  {% if stage['change'] %}<p class="note"><strong>What changed:</strong> {{ stage['change'] }}</p>{% endif %}
  <div class="link-row">
    {% if stage['report_href'] %}<a href="{{ stage['report_href'] }}">Experiment report</a>{% endif %}
  </div>
</article>
{%- endmacro %}
"""


_BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page.title }}</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4ede2;
      --surface: #fffaf2;
      --surface-strong: #fff5e8;
      --hero: linear-gradient(135deg, #f8dcc3 0%, #fff4e6 42%, #f6efe3 100%);
      --ink: #1f2d2f;
      --muted: #667578;
      --line: #dbcab2;
      --line-strong: #c9b08e;
      --accent: #0f766e;
      --accent-soft: #d7efea;
      --good: #166534;
      --good-bg: #e7f7eb;
      --warn: #a16207;
      --warn-bg: #fdf3d8;
      --bad: #b91c1c;
      --bad-bg: #fde8e8;
      --neutral-bg: #ece4d5;
      --shadow: 0 18px 40px rgba(32, 48, 51, 0.08);
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(255, 223, 186, 0.32), transparent 30%),
        linear-gradient(180deg, #faf4ea 0%, var(--bg) 100%);
    }
    main { max-width: 1520px; margin: 0 auto; padding: 24px; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    h1, h2, h3 { margin: 0 0 10px; line-height: 1.15; overflow-wrap: anywhere; }
    h1 { font-size: clamp(2rem, 4vw, 3.3rem); }
    h2 { font-size: 1.4rem; }
    h3 { font-size: 1.05rem; }
    p { margin: 0; line-height: 1.5; }
    section { margin: 22px 0; }
    .hero {
      background: var(--hero);
      border: 1px solid var(--line-strong);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 26px;
      position: relative;
      overflow: hidden;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -8% -28% auto;
      width: 240px;
      height: 240px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(15, 118, 110, 0.12), transparent 65%);
      pointer-events: none;
    }
    .hero-top { display: flex; justify-content: space-between; gap: 20px; align-items: start; }
    .hero-copy { max-width: 900px; display: grid; gap: 10px; }
    .eyebrow {
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .hero-summary { font-size: 1.08rem; max-width: 88ch; overflow-wrap: anywhere; }
    .chip-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.78rem;
      font-weight: 700;
      border: 1px solid transparent;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      overflow-wrap: anywhere;
    }
    .badge-good { background: var(--good-bg); color: var(--good); border-color: rgba(22, 101, 52, 0.18); }
    .badge-warn { background: var(--warn-bg); color: var(--warn); border-color: rgba(161, 98, 7, 0.18); }
    .badge-bad { background: var(--bad-bg); color: var(--bad); border-color: rgba(185, 28, 28, 0.18); }
    .badge-neutral { background: var(--neutral-bg); color: var(--ink); border-color: rgba(32, 48, 51, 0.08); }
    .hero-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-top: 18px; }
    .hero-meta-item { background: rgba(255, 255, 255, 0.48); border: 1px solid rgba(201, 176, 142, 0.5); border-radius: 8px; padding: 12px 14px; min-width: 0; }
    .hero-meta-item strong { display: block; font-size: 1.05rem; margin-top: 4px; overflow-wrap: anywhere; }
    .grid-3 { display: grid; gap: 16px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid-4 { display: grid; gap: 16px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .split-grid { display: grid; gap: 16px; grid-template-columns: 1.2fr 1fr; }
    .card {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
    }
    .metric-card { display: grid; gap: 8px; }
    .metric-value { font-size: clamp(1.45rem, 2.5vw, 2.1rem); font-weight: 700; overflow-wrap: anywhere; }
    .mini-value { font-size: 1.05rem; font-weight: 700; }
    .note, .section-subtitle, .cell-subtext, .lead, .cell-details, details summary { color: var(--muted); }
    .lead { margin-bottom: 10px; }
    .section-head { display: flex; gap: 16px; justify-content: space-between; align-items: end; margin-bottom: 14px; }
    .link-row { display: flex; gap: 12px; flex-wrap: wrap; }
    .bullet-list { margin: 0; padding-left: 20px; display: grid; gap: 8px; }
    .section-chips { margin-bottom: 10px; }
    .table-card { padding-bottom: 10px; }
    .table-wrap { overflow: auto; border-radius: 16px; border: 1px solid var(--line); }
    table { width: 100%; border-collapse: collapse; min-width: 920px; background: var(--surface); }
    th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
    th {
      position: sticky;
      top: 0;
      background: #efe2cc;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      cursor: pointer;
      z-index: 1;
    }
    tbody tr:nth-child(odd) { background: rgba(255, 248, 238, 0.74); }
    .align-right { text-align: right; }
    .align-center { text-align: center; }
    .cell-text { font-weight: 600; overflow-wrap: anywhere; }
    .cell-subtext, .cell-details, .note { overflow-wrap: anywhere; }
    .monospace { font-family: Consolas, "SFMono-Regular", monospace; font-size: 0.88rem; }
    details { margin-top: 6px; }
    .plot-grid { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .plot-card img { width: 100%; height: auto; display: block; border-radius: 14px; margin: 12px 0; border: 1px solid var(--line); }
    .plot-hero { grid-column: 1 / -1; }
    .guidance-grid { display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .empty-state {
      border: 1px dashed var(--line-strong);
      border-radius: 14px;
      padding: 18px;
      background: var(--surface-strong);
      color: var(--muted);
    }
    .stage-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    .stage-topline { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
    .metric-mini-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 14px 0; }
    .details-grid { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .detail-list { display: grid; gap: 10px; }
    .detail-item { border-top: 1px solid var(--line); padding-top: 10px; }
    .detail-item:first-child { border-top: 0; padding-top: 0; }
    @media (max-width: 1080px) {
      .grid-3, .grid-4, .split-grid, .details-grid, .guidance-grid, .plot-grid { grid-template-columns: 1fr; }
      table { min-width: 760px; }
    }
    @media (max-width: 720px) {
      main { padding: 16px; }
      .hero { padding: 20px; }
      .hero-top { flex-direction: column; }
      .hero-meta { grid-template-columns: 1fr; }
      .metric-mini-grid { grid-template-columns: 1fr; }
      table { min-width: 640px; }
    }
  </style>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      for (const table of document.querySelectorAll('table[data-sortable="true"]')) {
        const headers = Array.from(table.querySelectorAll('thead th'));
        headers.forEach((header, index) => {
          let ascending = true;
          header.addEventListener('click', () => {
            const sortType = header.dataset.sort || 'string';
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            rows.sort((a, b) => {
              const aValue = a.children[index].dataset.sortValue || '';
              const bValue = b.children[index].dataset.sortValue || '';
              if (sortType === 'number') {
                const aNum = Number(aValue);
                const bNum = Number(bValue);
                return ascending ? aNum - bNum : bNum - aNum;
              }
              return ascending ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
            });
            ascending = !ascending;
            rows.forEach((row) => tbody.appendChild(row));
          });
        });
      }
    });
  </script>
</head>
<body>
  <main>
    {% block body %}{% endblock %}
  </main>
</body>
</html>
"""


_EXPERIMENT_TEMPLATE = """
{% extends 'base.html' %}
{% import 'components.html' as ui %}
{% block body %}
<section class="hero">
  <div class="hero-top">
    <div class="hero-copy">
      <div class="chip-row">
        {% for item in page.top_badges %}{{ ui.badge(item['text'], item['tone']) }}{% endfor %}
      </div>
      <h1>{{ page.title }}</h1>
      <div class="eyebrow">Main Conclusion</div>
      <p class="hero-summary">{{ page.summary_sentence }}</p>
    </div>
  </div>
  <div class="hero-meta">
    {% for item in page.hero_meta %}
    <div class="hero-meta-item">
      <div class="eyebrow">{{ item.label }}</div>
      <strong>{{ item['value'] }}</strong>
      {% if item['note'] %}<div class="note">{{ item['note'] }}</div>{% endif %}
    </div>
    {% endfor %}
  </div>
</section>

{% if page.executive_cards %}
<section class="grid-4">
  {% for card in page.executive_cards %}{{ ui.metric_card(card) }}{% endfor %}
</section>
{% endif %}

<section class="grid-3">
  {% for section in page.decision_cards %}{{ ui.bullet_card(section) }}{% endfor %}
</section>

{% if page.study_cards %}
<section class="grid-3">
  {% for card in page.study_cards %}{{ ui.bullet_card(card) }}{% endfor %}
</section>
{% endif %}

{{ ui.table_card(page.candidate_table) }}

{% if page.plots %}
<section>
  <div class="section-head">
    <div>
      <h2>Evidence Layer</h2>
      <p class="section-subtitle">Decision-useful plots only, each with explicit reading guidance.</p>
    </div>
  </div>
  <div class="plot-grid">
    {% for plot in page.plots %}{{ ui.plot_card(plot) }}{% endfor %}
  </div>
</section>
{% endif %}

<section class="details-grid">
  <article class="card">
    <h2>Artifacts</h2>
    <div class="detail-list">
      {% for item in page.artifact_links %}
      <div class="detail-item">
        <div class="eyebrow">{{ item['label'] }}</div>
        <div><a href="{{ item['href'] }}">{{ item['text'] }}</a></div>
      </div>
      {% endfor %}
    </div>
  </article>
  <article class="card">
    <h2>Provenance And Diagnostics</h2>
    <div class="detail-list">
      {% for item in page.provenance_items %}
      <div class="detail-item">
        <div class="eyebrow">{{ item['label'] }}</div>
        <div>{{ item['value'] }}</div>
        {% if item['note'] %}<div class="note">{{ item['note'] }}</div>{% endif %}
      </div>
      {% endfor %}
    </div>
  </article>
</section>
{% endblock %}
"""


_OVERNIGHT_TEMPLATE = """
{% extends 'base.html' %}
{% import 'components.html' as ui %}
{% block body %}
<section class="hero">
  <div class="hero-top">
    <div class="hero-copy">
      <div class="chip-row">
        {% for item in page.top_badges %}{{ ui.badge(item['text'], item['tone']) }}{% endfor %}
      </div>
      <h1>{{ page.title }}</h1>
      <div class="eyebrow">Main Conclusion</div>
      <p class="hero-summary">{{ page.summary_sentence }}</p>
    </div>
  </div>
  <div class="hero-meta">
    {% for item in page.hero_meta %}
    <div class="hero-meta-item">
      <div class="eyebrow">{{ item.label }}</div>
      <strong>{{ item['value'] }}</strong>
      {% if item['note'] %}<div class="note">{{ item['note'] }}</div>{% endif %}
    </div>
    {% endfor %}
  </div>
</section>

{% if page.executive_cards %}
<section class="grid-4">
  {% for card in page.executive_cards %}{{ ui.metric_card(card) }}{% endfor %}
</section>
{% endif %}

<section class="grid-3">
  {% for section in page.decision_cards %}{{ ui.bullet_card(section) }}{% endfor %}
</section>

<section>
  <div class="section-head">
    <div>
      <h2>Stage Evolution</h2>
      <p class="section-subtitle">Each stage card shows the winning configuration, trust signals, and what changed versus the prior stage.</p>
    </div>
  </div>
  <div class="stage-grid">
    {% for stage in page.stage_cards %}{{ ui.stage_card(stage) }}{% endfor %}
  </div>
</section>

{{ ui.table_card(page.stage_table) }}
{{ ui.table_card(page.candidate_table) }}

{% if page.plots %}
<section>
  <div class="section-head">
    <div>
      <h2>Pipeline Evidence</h2>
      <p class="section-subtitle">Top-level plots explain score evolution, runtime concentration, and frontier movement across stages.</p>
    </div>
  </div>
  <div class="plot-grid">
    {% for plot in page.plots %}{{ ui.plot_card(plot) }}{% endfor %}
  </div>
</section>
{% endif %}

<section class="details-grid">
  <article class="card">
    <h2>Artifacts</h2>
    <div class="detail-list">
      {% for item in page.artifact_links %}
      <div class="detail-item">
        <div class="eyebrow">{{ item['label'] }}</div>
        <div><a href="{{ item['href'] }}">{{ item['text'] }}</a></div>
      </div>
      {% endfor %}
    </div>
  </article>
  <article class="card">
    <h2>Pipeline Provenance</h2>
    <div class="detail-list">
      {% for item in page.provenance_items %}
      <div class="detail-item">
        <div class="eyebrow">{{ item['label'] }}</div>
        <div>{{ item['value'] }}</div>
        {% if item['note'] %}<div class="note">{{ item['note'] }}</div>{% endif %}
      </div>
      {% endfor %}
    </div>
  </article>
</section>
{% endblock %}
"""


_ENV = Environment(
    loader=DictLoader(
        {
            "base.html": _BASE_TEMPLATE,
            "components.html": _COMPONENTS_TEMPLATE,
            "experiment.html": _EXPERIMENT_TEMPLATE,
            "overnight.html": _OVERNIGHT_TEMPLATE,
        }
    ),
    autoescape=select_autoescape(enabled_extensions=("html",)),
)


def render_template(name: str, **context: object) -> str:
    return _ENV.get_template(name).render(**context)
