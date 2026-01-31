#!/usr/bin/env python3
"""
PROGRESS.json更新スクリプト

使用方法:
    python3 tools/update_progress.py --commit "コミットメッセージ"
    python3 tools/update_progress.py --task-complete "39b" --description "Two-Tier Entry System実装完了"
    python3 tools/update_progress.py --task-start "39c" --description "Multi-Timeframe Integration実装開始"
"""

import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


def get_git_info():
    """最新のGit情報を取得"""
    try:
        # 最新コミットハッシュ
        commit_hash = subprocess.check_output(
            ['git', 'log', '-1', '--format=%h'],
            text=True
        ).strip()
        
        # 最新コミットメッセージ
        commit_message = subprocess.check_output(
            ['git', 'log', '-1', '--format=%s'],
            text=True
        ).strip()
        
        # 変更統計
        stats = subprocess.check_output(
            ['git', 'show', '--stat', '--format=', commit_hash],
            text=True
        ).strip()
        
        return {
            'hash': commit_hash,
            'message': commit_message,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"Git情報取得エラー: {e}")
        return None


def load_progress():
    """PROGRESS.jsonを読み込み"""
    progress_file = Path(__file__).parent.parent / 'PROGRESS.json'
    
    if not progress_file.exists():
        print(f"エラー: {progress_file} が見つかりません")
        return None
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_progress(data):
    """PROGRESS.jsonに保存"""
    progress_file = Path(__file__).parent.parent / 'PROGRESS.json'
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ PROGRESS.json更新完了: {progress_file}")


def update_latest_commit(data):
    """最新コミット情報を更新"""
    git_info = get_git_info()
    if git_info:
        data['latest_commit'].update(git_info)
        data['project']['last_updated'] = git_info['date']
        print(f"✅ 最新コミット情報を更新: {git_info['hash']} - {git_info['message']}")
    return data


def complete_task(data, task_id, description):
    """タスク完了を記録"""
    # in_progressから削除
    in_progress = data['current_status']['active_tasks']['in_progress']
    task_found = None
    
    for i, task in enumerate(in_progress):
        if task['task_id'] == task_id:
            task_found = in_progress.pop(i)
            break
    
    # next_priorityからも削除
    if not task_found:
        next_priority = data['current_status']['active_tasks']['next_priority']
        for i, task in enumerate(next_priority):
            if task['task_id'] == task_id:
                task_found = next_priority.pop(i)
                break
    
    if task_found:
        # recently_completedに追加
        completed_task = {
            'task_id': task_id,
            'title': task_found.get('title', description),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'description': description
        }
        
        data['current_status']['recently_completed'].insert(0, completed_task)
        
        # 最新5件のみ保持
        data['current_status']['recently_completed'] = \
            data['current_status']['recently_completed'][:5]
        
        print(f"✅ タスク完了を記録: {task_id} - {description}")
    else:
        print(f"⚠️  警告: タスク {task_id} がin_progress/next_priorityに見つかりません")
    
    return data


def start_task(data, task_id, description, priority="★★★★☆"):
    """タスク開始を記録"""
    # next_priorityから削除
    next_priority = data['current_status']['active_tasks']['next_priority']
    task_found = None
    
    for i, task in enumerate(next_priority):
        if task['task_id'] == task_id:
            task_found = next_priority.pop(i)
            break
    
    # in_progressに追加
    new_task = {
        'task_id': task_id,
        'title': task_found['title'] if task_found else description,
        'status': '実装中',
        'priority': priority
    }
    
    data['current_status']['active_tasks']['in_progress'].append(new_task)
    
    print(f"✅ タスク開始を記録: {task_id} - {description}")
    return data


def main():
    parser = argparse.ArgumentParser(description='PROGRESS.json更新ツール')
    parser.add_argument('--commit', action='store_true',
                        help='最新コミット情報を更新')
    parser.add_argument('--task-complete', metavar='TASK_ID',
                        help='タスク完了を記録（例: 39b）')
    parser.add_argument('--task-start', metavar='TASK_ID',
                        help='タスク開始を記録（例: 39c）')
    parser.add_argument('--description', metavar='DESC',
                        help='タスクの説明')
    parser.add_argument('--priority', metavar='PRIORITY',
                        default='★★★★☆',
                        help='タスクの優先度（デフォルト: ★★★★☆）')
    
    args = parser.parse_args()
    
    # PROGRESS.json読み込み
    data = load_progress()
    if not data:
        return 1
    
    # コミット情報更新
    if args.commit:
        data = update_latest_commit(data)
    
    # タスク完了
    if args.task_complete:
        if not args.description:
            print("エラー: --descriptionが必要です")
            return 1
        data = complete_task(data, args.task_complete, args.description)
    
    # タスク開始
    if args.task_start:
        if not args.description:
            print("エラー: --descriptionが必要です")
            return 1
        data = start_task(data, args.task_start, args.description, args.priority)
    
    # 保存
    save_progress(data)
    
    return 0


if __name__ == '__main__':
    exit(main())
