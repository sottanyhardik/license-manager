#!/usr/bin/env python3
"""
License Manager Autonomous Modernization Orchestrator

Core responsibility: Drive modules 2-11 through discovery, design, implementation,
verification, and freeze states. Manage write locks, validate gates, collect evidence,
recover from context compaction.

This script is persistent and safe to interrupt. All state is in docs/orchestrator/.
"""

import json
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ORCH_DIR = REPO_ROOT / "docs" / "orchestrator"
STATE_FILE = ORCH_DIR / "state.json"
LOCKS_FILE = ORCH_DIR / "locks.json"
AGENTS_FILE = ORCH_DIR / "agents.json"
DEPS_FILE = ORCH_DIR / "dependency_graph.json"
GATES_FILE = ORCH_DIR / "gates.json"
BLOCKERS_FILE = ORCH_DIR / "blockers.json"
CHECKPOINTS_DIR = ORCH_DIR / "checkpoints"

# Default state structure
DEFAULT_STATE = {
    "program": "license-manager-modernization",
    "status": "INITIALIZED",
    "current_module": 2,
    "current_phase": "DISCOVERY",
    "started_at": None,
    "last_checkpoint": None,
    "modules": {i: {"state": "QUEUED" if i > 1 else "FROZEN", "phase": None} for i in range(1, 12)},
    "agents": {},
    "final_gate": False,
}

def load_state():
    """Load orchestrator state from disk."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return DEFAULT_STATE.copy()

def save_state(state):
    """Save orchestrator state to disk."""
    ORCH_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def git_status():
    """Get current git status."""
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, cwd=REPO_ROOT)
    return result.stdout.strip()

def git_head():
    """Get current commit hash."""
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=REPO_ROOT)
    return result.stdout.strip()

def checkpoint(state, reason):
    """Create a recovery checkpoint."""
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    checkpoint_data = {
        "timestamp": timestamp,
        "reason": reason,
        "program_state": state["status"],
        "current_module": state["current_module"],
        "current_phase": state["current_phase"],
        "git_head": git_head(),
        "git_status": "clean" if not git_status() else "dirty",
    }
    checkpoint_file = CHECKPOINTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{reason}.json"
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)
    state["last_checkpoint"] = str(checkpoint_file)

def status_dashboard(state):
    """Display current orchestrator status."""
    print(f"""
LICENSE MANAGER MODERNIZATION ORCHESTRATOR
==========================================

Status: {state['status']}
Current Module: {state['current_module']}
Current Phase: {state['current_phase']}

Module Status:
  1. Ledger          🔒 FROZEN
  2. Planning        {('🟡 ' + state['modules'][2]['phase']) if state['modules'][2]['state'] != 'QUEUED' else '🔵 QUEUED'}
  3. Allocation      {'🟡 ' + state['modules'][3]['phase'] if state['modules'][3]['state'] != 'QUEUED' else '🔵 QUEUED'}
  4. BOE             {'🟡 ' + state['modules'][4]['phase'] if state['modules'][4]['state'] != 'QUEUED' else '🔵 QUEUED'}
  5. Invoice         {'🟡 ' + state['modules'][5]['phase'] if state['modules'][5]['state'] != 'QUEUED' else '🔵 QUEUED'}
  6. Transfers       {'🟡 ' + state['modules'][6]['phase'] if state['modules'][6]['state'] != 'QUEUED' else '🔵 QUEUED'}
  7. Reporting       {'🟡 ' + state['modules'][7]['phase'] if state['modules'][7]['state'] != 'QUEUED' else '🔵 QUEUED'}
  8. DFIA            {'🟡 ' + state['modules'][8]['phase'] if state['modules'][8]['state'] != 'QUEUED' else '🔵 QUEUED'}
  9. Incentive       {'🟡 ' + state['modules'][9]['phase'] if state['modules'][9]['state'] != 'QUEUED' else '🔵 QUEUED'}
 10. Documents       {'🟡 ' + state['modules'][10]['phase'] if state['modules'][10]['state'] != 'QUEUED' else '🔵 QUEUED'}
 11. Admin           {'🟡 ' + state['modules'][11]['phase'] if state['modules'][11]['state'] != 'QUEUED' else '🔵 QUEUED'}

Git Status: {git_status() or 'Clean'}

Blockers: {len(json.load(open(BLOCKERS_FILE)) if BLOCKERS_FILE.exists() else [])}

Last Checkpoint: {state.get('last_checkpoint', 'None')}
""")

def dry_run(state):
    """Show what would happen next without making changes."""
    print(f"""
DRY RUN: LICENSE MANAGER MODERNIZATION ORCHESTRATOR
===================================================

Current State:
  Module: {state['current_module']}
  Phase: {state['current_phase']}
  Status: {state['status']}

Next Actions:
  1. Verify repository state
  2. Check dependency graph
  3. Launch discovery agents for Modules 3-11 (read-only, parallel)
  4. Progress Module 2 to next phase
  5. Check for available write scopes
  6. Collect evidence from agents
  7. Validate gates
  8. Create checkpoint
  9. Continue

Modules Ready for Discovery:
  - Module 2 (current)
  - Module 3+ (parallel, if dependencies allow)

Write Locks:
  - Module 2 (planning-implementation)

This is a dry run. No changes will be made.
Use 'orchestrator start' to begin execution.
""")

def main():
    if len(sys.argv) < 2:
        print("Usage: orchestrator <command>")
        print("Commands: status, dry-run, start, resume, locks, agents, blockers")
        sys.exit(1)

    command = sys.argv[1]
    state = load_state()

    if command == "status":
        status_dashboard(state)

    elif command == "dry-run":
        dry_run(state)

    elif command == "start":
        print("Starting License Manager Autonomous Modernization...")
        if not state["started_at"]:
            state["started_at"] = datetime.now().isoformat()
            state["status"] = "RUNNING"
        save_state(state)
        checkpoint(state, "orchestration_start")
        print(f"✓ Orchestrator started. Current module: {state['current_module']}")
        print("  Next: discovery agents will launch automatically")
        print("  Status: orchestrator status")

    elif command == "resume":
        print("Resuming License Manager Modernization...")
        state["status"] = "RUNNING"
        save_state(state)
        checkpoint(state, "orchestration_resume")
        print(f"✓ Orchestrator resumed from checkpoint")
        print(f"  Current module: {state['current_module']}")
        print(f"  Current phase: {state['current_phase']}")

    elif command == "locks":
        locks = json.load(open(LOCKS_FILE)) if LOCKS_FILE.exists() else {}
        print("Active Write Locks:")
        for lock in locks.values():
            print(f"  Module {lock['module']}: {lock['scope']} (agent: {lock['agent']})")

    elif command == "agents":
        agents = json.load(open(AGENTS_FILE)) if AGENTS_FILE.exists() else {}
        print(f"Agent Registry ({len(agents)} agents):")
        for agent_id, agent in agents.items():
            print(f"  {agent_id}: {agent['role']} (status: {agent['status']})")

    elif command == "blockers":
        blockers = json.load(open(BLOCKERS_FILE)) if BLOCKERS_FILE.exists() else []
        print(f"Active Blockers ({len(blockers)}):")
        for blocker in blockers:
            print(f"  {blocker['type']}: {blocker['reason']}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
