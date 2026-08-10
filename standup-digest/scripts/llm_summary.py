import json
import sys
from collections import defaultdict

def normalize_name(name):
    if not name or name == 'unknown':
        return 'unknown'
    return name.split('/')[-1]

def create_llm_summary(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    window = data.get('window', {})
    start_date = window.get('since', 'unknown')[:10]
    
    print(f"DATE: {start_date}")
    print(f"WARNINGS: {data.get('warnings', [])}")
    print(f"STATS: {data.get('stats', {})}")
    print("\n")
    
    # group commits by repo
    commits_by_repo = defaultdict(list)
    for c in data.get('commits', []):
        repo = c.get('repo')
        if not repo:
            repo = c.get('path', 'unknown').split('/')[-1] + ' (local, no remote)'
        else:
            repo = normalize_name(repo)
        commits_by_repo[repo].append(c)

    ws_map = {}
    for ws in data.get('working_state', []):
        ws_map[ws.get('path')] = ws
        
    projects = defaultdict(list)
    for s in data.get('sessions', []):
        proj = normalize_name(s.get('project', 'unknown'))
        projects[proj].append(s)
        
    for proj, sessions in projects.items():
        print(f"### PROJECT: {proj}")
        
        if proj in commits_by_repo:
            print("  COMMITS:")
            for c in commits_by_repo[proj]:
                print(f"    - {c.get('sha')[:7]} {c.get('subject')}")
                
        for s in sessions:
            title = s.get('title')
            if not title:
                prompts = s.get('prompts', [])
                title = (prompts[0][:60] + "...") if prompts else "session with no recorded prompts"
                
            print(f"  * SESSION: {title}")
            print(f"    - Launch: {s.get('launch')}")
            print(f"    - Branches: {s.get('branches')}")
            
            # Print refs
            refs = s.get('refs', [])
            if refs:
                print("    - Refs:")
                for r in refs:
                    print(f"      - {r.get('kind')} #{r.get('number')} ({r.get('state')}) [verified: {r.get('verification')}]")
                    
            # Print working states
            cwds = s.get('cwds', [])
            for cwd in cwds:
                if cwd in ws_map:
                    ws = ws_map[cwd]
                    print(f"    - Working state: path={ws.get('path')}, dirty={ws.get('dirty_files')}, branch={ws.get('branch')}, last_commit={ws.get('last_commit', {}).get('sha') if ws.get('last_commit') else 'null'}")
                    
            # Prompts/Notes summary
            prompts = s.get('prompts', [])
            notes = s.get('assistant_notes', [])
            p_text = prompts[0][:150].replace('\n', ' ') if prompts else ""
            n_text = notes[0][:150].replace('\n', ' ') if notes else ""
            if p_text or n_text:
                print(f"    - Context: {p_text} | {n_text}")

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("Usage: python llm_summary.py <path_to_json>")
        sys.exit(1)
    try:
        create_llm_summary(sys.argv[1])
    except BrokenPipeError:
        import os
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)
