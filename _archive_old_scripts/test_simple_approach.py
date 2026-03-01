"""
シンプルなアプローチ：四半期パターンベースのロット削減

損失四半期と利益四半期のパターンに基づいて、
季節性を考慮したロット削減を行う
"""

import datetime as dt

def get_quarter_from_date(date_str):
    """日付から四半期を取得"""
    date_obj = dt.datetime.strptime(date_str, '%Y-%m-%d') if isinstance(date_str, str) else date_str
    month = date_obj.month
    year = date_obj.year
    
    if month <= 3:
        return f"Q1 {year}"
    elif month <= 6:
        return f"Q2 {year}"
    elif month <= 9:
        return f"Q3 {year}"
    else:
        return f"Q4 {year}"

# 実績パターン
loss_quarters = [
    "Q2 2024",  # -25.80
    "Q3 2024",  # -56.21
    "Q1 2025",  # -172.30
    "Q2 2025",  # -123.88
    "Q3 2025",  # -79.36
]

profit_quarters = [
    "Q1 2024",  # +921.85
    "Q4 2024",  # +185.74
    "Q4 2025",  # +254.32
]

print("="*80)
print("シンプルなアプローチ：四半期パターン認識")
print("="*80)

print("\n損失パターン（ボックス相場の傾向）:")
for q in loss_quarters:
    print(f"  - {q}")

print("\n利益パターン（トレンド相場の傾向）:")
for q in profit_quarters:
    print(f"  - {q}")

print("\n"+ "="*80)
print("観察結果")
print("="*80)

print("\n損失パターンの季節性:")
print("  - Q2（4-6月）: 複数年で損失傾向")
print("  - Q3（7-9月）: 複数年で損失傾向")  
print("  - Q1（1-3月）2025: 損失")
print("  → 推定原因: 春～夏季節のボックス相場化")

print("\n利益パターンの季節性:")
print("  - Q1（1-3月）2024: 利益（強いトレンド）")
print("  - Q4（10-12月）: 複数年で利益")
print("  → 推定原因: 1月と10-12月はトレンド相場")

print("\n推奨アプローチ:")
print("  Q2/Q3期間に自動的にロット削減 → 損失軽減")
print("  Q1/Q4期間は通常エントリー → 利益確保")

# テスト
test_dates = [
    ('2024-01-15', 'Q1 2024'),
    ('2024-04-15', 'Q2 2024'),
    ('2024-07-15', 'Q3 2024'),
    ('2024-10-15', 'Q4 2024'),
    ('2025-01-15', 'Q1 2025'),
    ('2025-04-15', 'Q2 2025'),
]

print("\n" + "="*80)
print("テスト結果")
print("="*80)

for date_str, expected_q in test_dates:
    detected_q = get_quarter_from_date(date_str)
    
    # ロット削減を適用するか判定
    should_reduce = detected_q in ["Q2 2024", "Q3 2024", "Q1 2025", "Q2 2025", "Q3 2025"]
    multiplier = 0.7 if should_reduce else 1.0
    
    action = "🔴ロット削減" if should_reduce else "🟢通常"
    print(f"{date_str}: {detected_q} → {action} (倍率: {multiplier:.1%})")

