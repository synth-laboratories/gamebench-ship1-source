from __future__ import annotations

from collections import deque
from typing import Any


DIRS = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
}


def plan_actions(scenario: dict[str, Any], objective: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Strong extract-oriented reference policy for DungeonGrid singleplayer."""

    max_actions = int((objective or {}).get("max_actions", scenario.get("max_steps", 100)))
    lines = str(scenario["map_ascii"]).splitlines()
    roles = list(scenario.get("hero_roles") or ["barbarian"])
    is_wizard = str(roles[0]) == "wizard"
    seed = int(scenario.get("seed", 0))

    def find(target: str) -> list[tuple[int, int]]:
        return [(x, y) for y, row in enumerate(lines) for x, ch in enumerate(row) if ch == target]

    entry = find("E")[0]
    doors = find("D")
    chests = find("C")
    monsters = find("R")
    objectives = find("I")

    door_ids = {pos: f"door_{i}" for i, pos in enumerate(doors, start=1)}
    chest_ids = {pos: f"chest_{i}" for i, pos in enumerate(chests, start=1)}
    monster_ids = {pos: f"crypt_brute_{i}" for i, pos in enumerate(monsters, start=1)}

    walkable = {
        (x, y)
        for y, row in enumerate(lines)
        for x, ch in enumerate(row)
        if ch in {".", "E", "I", "D", "T", "C", "R"}
    }

    def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def neighbors(pos: tuple[int, int]) -> list[tuple[str, tuple[int, int]]]:
        x, y = pos
        out: list[tuple[str, tuple[int, int]]] = []
        for direction, (dx, dy) in DIRS.items():
            nxt = (x + dx, y + dy)
            if nxt in walkable:
                out.append((direction, nxt))
        return out

    def bfs(start: tuple[int, int], goals: set[tuple[int, int]]) -> list[str] | None:
        if not goals:
            return None
        if start in goals:
            return []
        queue: deque[tuple[tuple[int, int], list[str]]] = deque([(start, [])])
        seen = {start}
        while queue:
            pos, path = queue.popleft()
            for direction, nxt in neighbors(pos):
                if nxt in seen:
                    continue
                seen.add(nxt)
                nxt_path = path + [direction]
                if nxt in goals:
                    return nxt_path
                queue.append((nxt, nxt_path))
        return None

    def adjacent_tiles(targets: list[tuple[int, int]]) -> set[tuple[int, int]]:
        tiles: set[tuple[int, int]] = set()
        for tx, ty in targets:
            for dx, dy in DIRS.values():
                cand = (tx + dx, ty + dy)
                if cand in walkable:
                    tiles.add(cand)
            if (tx, ty) in walkable:
                tiles.add((tx, ty))
        return tiles

    actions: list[dict[str, Any]] = []
    pos = entry
    ap = 2
    opened_doors: set[tuple[int, int]] = set()
    opened_chests: set[tuple[int, int]] = set()
    defeated: set[tuple[int, int]] = set()
    has_objective = False
    revealed = False
    armored = False

    def emit(action: dict[str, Any], cost: int) -> bool:
        nonlocal ap
        if len(actions) >= max_actions:
            return False
        if cost > ap:
            actions.append({"type": "end_turn"})
            ap = 2
            if len(actions) >= max_actions:
                return False
        actions.append(action)
        ap -= cost
        if ap <= 0:
            if len(actions) < max_actions:
                actions.append({"type": "end_turn"})
            ap = 2
        return len(actions) < max_actions

    emit({"type": "message", "target": "party", "payload": {"text": "DG|SCOUT;EXTRACT"}}, 1)

    def handle_monster(target: tuple[int, int]) -> None:
        nonlocal revealed
        if target in defeated or target not in monster_ids:
            return
        if is_wizard and not revealed:
            emit(
                {
                    "type": "cast",
                    "target": monster_ids[target],
                    "payload": {"spell": "reveal_glyph"},
                },
                2,
            )
            revealed = True
        for _ in range(2):
            if is_wizard:
                emit(
                    {
                        "type": "cast",
                        "target": monster_ids[target],
                        "payload": {"spell": "spark_lance"},
                    },
                    2,
                )
            else:
                emit({"type": "attack_melee", "target": monster_ids[target]}, 2)
        defeated.add(target)

    def step_toward(goals: set[tuple[int, int]]) -> bool:
        nonlocal pos
        path = bfs(pos, goals)
        if path is None:
            return False
        if not path:
            return True
        direction = path[0]
        dx, dy = DIRS[direction]
        nxt = (pos[0] + dx, pos[1] + dy)
        if nxt in door_ids and nxt not in opened_doors:
            if not emit({"type": "open_door", "target": door_ids[nxt]}, 1):
                return False
            opened_doors.add(nxt)
        if nxt in monster_ids and nxt not in defeated:
            handle_monster(nxt)
        if not emit({"type": "move", "direction": direction}, 1):
            return False
        pos = nxt
        return True

    safety = 0
    while len(actions) < max_actions and safety < max_actions * 4:
        safety += 1
        for monster in monsters:
            if monster not in defeated and manhattan(pos, monster) == 1:
                handle_monster(monster)
        for chest_pos, chest_id in chest_ids.items():
            if chest_pos in opened_chests:
                continue
            if manhattan(pos, chest_pos) <= 1:
                if not emit({"type": "interact", "target": chest_id}, 1):
                    break
                opened_chests.add(chest_pos)
                if not armored:
                    armor = "iron_armor" if (seed + 1) % 2 else "leather_armor"
                    emit({"type": "use_item", "target": armor}, 1)
                    armored = True
        if not has_objective and objectives and manhattan(pos, objectives[0]) <= 1:
            if emit({"type": "interact", "target": "objective"}, 1):
                has_objective = True
        if has_objective and pos == entry:
            emit({"type": "interact", "target": "escape"}, 1)
            break
        if chests and not opened_chests.issuperset(set(chests)):
            if not step_toward(adjacent_tiles(chests)):
                break
            continue
        if objectives and not has_objective:
            if not step_toward(adjacent_tiles(objectives)):
                break
            continue
        if has_objective and pos != entry:
            if not step_toward({entry}):
                break
            continue
        if not emit({"type": "guard"}, 1):
            break

    return actions[:max_actions]
