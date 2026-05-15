#!/usr/bin/env python3
"""
ACTION_LIST.json → docs/action_list.html 変換スクリプト
prj-update 実行時に自動で呼び出される
"""
import json
import os
from datetime import datetime

SRC = os.path.join(os.path.dirname(__file__), '..', 'ACTION_LIST.json')
DST = os.path.join(os.path.dirname(__file__), '..', 'docs', 'action_list.html')

PRIORITY_STARS = {5: '★★★★★', 4: '★★★★☆', 3: '★★★☆☆', 2: '★★☆☆☆', 1: '★☆☆☆☆'}
PRIORITY_COLOR = {5: '#c0392b', 4: '#e67e22', 3: '#f1c40f', 2: '#27ae60', 1: '#95a5a6'}

def priority_label(p):
    if isinstance(p, int):
        return PRIORITY_STARS.get(p, str(p))
    return str(p)

def priority_color(p):
    if isinstance(p, int):
        return PRIORITY_COLOR.get(p, '#888')
    return '#888'

def escape(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def category_badge(cat):
    colors = {
        'PDCA検証': '#3498db',
        '仕様改善': '#9b59b6',
        '機能強化': '#1abc9c',
        'バグ修正': '#e74c3c',
        'インフラ': '#95a5a6',
        '戦略': '#e67e22',
    }
    c = colors.get(cat, '#7f8c8d')
    return f'<span class="badge" style="background:{c}">{escape(cat)}</span>'

def render_todo_table(tasks):
    if not tasks:
        return '<p class="empty">現在 TODO タスクはありません</p>'
    sorted_tasks = sorted(tasks, key=lambda t: t.get('priority', 0) if isinstance(t.get('priority', 0), int) else 0, reverse=True)
    rows = []
    for t in sorted_tasks:
        tid = escape(t.get('id', ''))
        cat = t.get('category', '')
        title = escape(t.get('title', ''))
        p = t.get('priority', 0)
        desc = escape(t.get('description', ''))
        pstar = priority_label(p)
        pcol = priority_color(p)
        rows.append(f'''
        <tr>
          <td class="id-cell"><code>{tid}</code></td>
          <td>{category_badge(cat)}</td>
          <td class="title-cell">{title}
            <div class="desc">{desc}</div>
          </td>
          <td style="color:{pcol};font-weight:bold;white-space:nowrap">{pstar}</td>
        </tr>''')
    return f'''
    <table>
      <thead><tr><th>ID</th><th>カテゴリ</th><th>タイトル / 説明</th><th>優先度</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>'''

def render_progress_table(tasks):
    if not tasks:
        return '<p class="empty">現在 進行中タスクはありません</p>'
    rows = []
    for t in tasks:
        tid = escape(t.get('id', ''))
        cat = t.get('category', '')
        title = escape(t.get('title', ''))
        started = escape(t.get('started_date', t.get('started_at', '')))
        desc = escape(t.get('description', ''))
        rows.append(f'''
        <tr>
          <td class="id-cell"><code>{tid}</code></td>
          <td>{category_badge(cat)}</td>
          <td class="title-cell">{title}
            <div class="desc">{desc}</div>
          </td>
          <td>{started}</td>
        </tr>''')
    return f'''
    <table>
      <thead><tr><th>ID</th><th>カテゴリ</th><th>タイトル / 説明</th><th>開始日</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>'''

def render_done_table(tasks):
    if not tasks:
        return '<p class="empty">完了タスクはありません</p>'
    # 完了日降順
    def sort_key(t):
        d = t.get('completed_date') or t.get('completed_at', '')
        return d
    sorted_tasks = sorted(tasks, key=sort_key, reverse=True)
    rows = []
    for t in sorted_tasks:
        tid = escape(t.get('id', ''))
        cat = t.get('category', '')
        title = escape(t.get('title', ''))
        completed = escape(t.get('completed_date') or t.get('completed_at', ''))
        result = escape(t.get('result', ''))
        desc = escape(t.get('description', ''))
        result_col = '#27ae60' if '採用' in result else ('#c0392b' if '不採用' in result else '#555')
        rows.append(f'''
        <tr>
          <td class="id-cell"><code>{tid}</code></td>
          <td>{category_badge(cat)}</td>
          <td class="title-cell">{title}
            <div class="desc">{desc}</div>
          </td>
          <td style="color:{result_col};font-weight:bold">{result}</td>
          <td class="date-cell">{completed}</td>
        </tr>''')
    return f'''
    <table>
      <thead><tr><th>ID</th><th>カテゴリ</th><th>タイトル / 説明</th><th>結果</th><th>完了日</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>'''

def generate():
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)

    summary = data.get('summary', {})
    tasks = data.get('tasks', {})
    todo_list = tasks.get('todo', [])
    progress_list = tasks.get('progress', [])
    done_list = tasks.get('done', [])
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Action List — satosystem gen2</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; background: #0f1117; color: #e0e0e0; padding: 24px; }}
    h1 {{ font-size: 1.6rem; color: #fff; margin-bottom: 4px; }}
    .subtitle {{ color: #888; font-size: 0.85rem; margin-bottom: 32px; }}
    .summary-bar {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
    .summary-card {{ background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 10px; padding: 16px 24px; min-width: 120px; text-align: center; }}
    .summary-card .num {{ font-size: 2rem; font-weight: bold; }}
    .summary-card .label {{ font-size: 0.8rem; color: #888; margin-top: 4px; }}
    .todo-num {{ color: #e67e22; }}
    .prog-num {{ color: #3498db; }}
    .done-num {{ color: #27ae60; }}
    .section {{ margin-bottom: 40px; }}
    .section-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #2a2d3a; }}
    .section-title {{ font-size: 1.1rem; font-weight: bold; color: #fff; }}
    .section-count {{ background: #2a2d3a; color: #aaa; font-size: 0.8rem; padding: 2px 8px; border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th {{ background: #1a1d27; color: #aaa; text-align: left; padding: 10px 12px; font-weight: 600; border-bottom: 2px solid #2a2d3a; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #1e2130; vertical-align: top; }}
    tr:hover td {{ background: #1a1d27; }}
    .id-cell code {{ background: #2a2d3a; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; color: #7ec8e3; }}
    .title-cell {{ max-width: 480px; }}
    .desc {{ color: #888; font-size: 0.8rem; margin-top: 4px; line-height: 1.5; }}
    .date-cell {{ color: #888; white-space: nowrap; font-size: 0.82rem; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; color: #fff; white-space: nowrap; }}
    .empty {{ color: #555; font-style: italic; padding: 12px 0; }}
    .footer {{ color: #444; font-size: 0.78rem; margin-top: 40px; text-align: right; }}
    @media (max-width: 768px) {{
      body {{ padding: 12px; }}
      table {{ font-size: 0.8rem; }}
      .title-cell {{ max-width: 240px; }}
    }}
  </style>
</head>
<body>

<h1>📋 Action List — satosystem gen2</h1>
<p class="subtitle">自動生成: {generated_at} | ソース: ACTION_LIST.json</p>

<div class="summary-bar">
  <div class="summary-card"><div class="num todo-num">{summary.get('todo', len(todo_list))}</div><div class="label">TODO</div></div>
  <div class="summary-card"><div class="num prog-num">{summary.get('in_progress', len(progress_list))}</div><div class="label">進行中</div></div>
  <div class="summary-card"><div class="num done-num">{summary.get('done', len(done_list))}</div><div class="label">完了</div></div>
</div>

<div class="section">
  <div class="section-header">
    <span class="section-title">🚀 進行中</span>
    <span class="section-count">{len(progress_list)} 件</span>
  </div>
  {render_progress_table(progress_list)}
</div>

<div class="section">
  <div class="section-header">
    <span class="section-title">📌 TODO</span>
    <span class="section-count">{len(todo_list)} 件</span>
  </div>
  {render_todo_table(todo_list)}
</div>

<div class="section">
  <div class="section-header">
    <span class="section-title">✅ 完了</span>
    <span class="section-count">{len(done_list)} 件（最新順）</span>
  </div>
  {render_done_table(done_list)}
</div>

<p class="footer">satosystem gen2 &copy; 2026 | <a href="ACTION_LIST.json" style="color:#3498db">ACTION_LIST.json</a></p>
</body>
</html>
'''

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✅ 生成完了: docs/action_list.html ({len(done_list)}件完了 / {len(todo_list)}件TODO / {len(progress_list)}件進行中)')

if __name__ == '__main__':
    generate()
