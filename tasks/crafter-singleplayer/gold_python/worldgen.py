"""Native Python Crafter world generation compatible with crafter-rs."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


U32_MASK = 0xFFFFFFFF
U64_MASK = 0xFFFFFFFFFFFFFFFF
GRAD3 = (
    (0.7071067811865476, 0.7071067811865476, 0.0),
    (-0.7071067811865476, 0.7071067811865476, 0.0),
    (0.7071067811865476, -0.7071067811865476, 0.0),
    (-0.7071067811865476, -0.7071067811865476, 0.0),
    (0.7071067811865476, 0.0, 0.7071067811865476),
    (-0.7071067811865476, 0.0, 0.7071067811865476),
    (0.7071067811865476, 0.0, -0.7071067811865476),
    (-0.7071067811865476, 0.0, -0.7071067811865476),
    (0.0, 0.7071067811865476, 0.7071067811865476),
    (0.0, -0.7071067811865476, 0.7071067811865476),
    (0.0, 0.7071067811865476, -0.7071067811865476),
    (0.0, -0.7071067811865476, -0.7071067811865476),
    (0.7071067811865476, 0.7071067811865476, 0.0),
    (-0.7071067811865476, 0.7071067811865476, 0.0),
    (0.7071067811865476, -0.7071067811865476, 0.0),
    (-0.7071067811865476, -0.7071067811865476, 0.0),
    (0.7071067811865476, 0.0, 0.7071067811865476),
    (-0.7071067811865476, 0.0, 0.7071067811865476),
    (0.7071067811865476, 0.0, -0.7071067811865476),
    (-0.7071067811865476, 0.0, -0.7071067811865476),
    (0.0, 0.7071067811865476, 0.7071067811865476),
    (0.0, -0.7071067811865476, 0.7071067811865476),
    (0.0, 0.7071067811865476, -0.7071067811865476),
    (0.0, -0.7071067811865476, -0.7071067811865476),
    (0.5773502691896258, 0.5773502691896258, 0.5773502691896258),
    (-0.5773502691896258, 0.5773502691896258, 0.5773502691896258),
    (0.5773502691896258, -0.5773502691896258, 0.5773502691896258),
    (-0.5773502691896258, -0.5773502691896258, 0.5773502691896258),
    (0.5773502691896258, 0.5773502691896258, -0.5773502691896258),
    (-0.5773502691896258, 0.5773502691896258, -0.5773502691896258),
    (0.5773502691896258, -0.5773502691896258, -0.5773502691896258),
    (-0.5773502691896258, -0.5773502691896258, -0.5773502691896258),
)


@dataclass
class GeneratedWorld:
    tiles: list[list[str]]
    entities: list[dict[str, Any]]
    tunnels: list[list[bool]] = field(default_factory=list)
    rng: ChaCha8Rng | None = None


class XorShiftRng:
    def __init__(self, seed: int) -> None:
        data = [0] * 16
        data[0] = 1
        seed &= U32_MASK
        for idx in range(1, 4):
            start = idx * 4
            data[start] = seed & 0xFF
            data[start + 1] = (seed >> 8) & 0xFF
            data[start + 2] = (seed >> 16) & 0xFF
            data[start + 3] = (seed >> 24) & 0xFF
        self.x = _read_u32_le(data, 0)
        self.y = _read_u32_le(data, 4)
        self.z = _read_u32_le(data, 8)
        self.w = _read_u32_le(data, 12)

    def next_u32(self) -> int:
        x = self.x
        t = (x ^ ((x << 11) & U32_MASK)) & U32_MASK
        self.x = self.y
        self.y = self.z
        self.z = self.w
        w = self.w
        self.w = (w ^ (w >> 19) ^ (t ^ (t >> 8))) & U32_MASK
        return self.w


class ChaCha8Rng:
    def __init__(self, seed: int) -> None:
        self.state = _chacha_seed_from_u64(seed)
        self.buffer: list[int] = []
        self.index = 0

    def next_u32(self) -> int:
        if self.index >= len(self.buffer):
            self.buffer = self._refill4()
            self.index = 0
        value = self.buffer[self.index]
        self.index += 1
        return value

    def next_u64(self) -> int:
        low = self.next_u32()
        high = self.next_u32()
        return low | (high << 32)

    def random_f64(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def random_f32(self) -> float:
        return (self.next_u32() >> 8) * (1.0 / (1 << 24))

    def gen_range_u32_inclusive(self, low: int, high: int) -> int:
        assert low <= high
        return _sample_single_u32(self, low, high + 1)

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "state": list(self.state),
            "buffer": list(self.buffer),
            "index": int(self.index),
        }

    @classmethod
    def from_checkpoint(cls, payload: dict[str, Any]) -> "ChaCha8Rng":
        rng = cls(0)
        rng.state = [int(value) & U32_MASK for value in payload["state"]]
        rng.buffer = [int(value) & U32_MASK for value in payload.get("buffer", [])]
        rng.index = int(payload.get("index", len(rng.buffer)))
        return rng

    def _refill4(self) -> list[int]:
        out: list[int] = []
        base = list(self.state)
        for _ in range(4):
            block_state = list(base)
            for _round in range(4):
                _chacha_double_round(block_state)
            for idx, value in enumerate(block_state):
                out.append((value + base[idx]) & U32_MASK)
            base[12] = (base[12] + 1) & U32_MASK
            if base[12] == 0:
                base[13] = (base[13] + 1) & U32_MASK
        self.state[12] = base[12]
        self.state[13] = base[13]
        return out


class PermutationTable:
    def __init__(self, seed: int) -> None:
        rng = XorShiftRng(seed)
        values = list(range(256))
        for idx in range(255, 0, -1):
            swap_idx = _gen_index_u32(rng, idx + 1)
            values[idx], values[swap_idx] = values[swap_idx], values[idx]
        self.values = values

    def hash(self, coords: tuple[int, ...]) -> int:
        index: int | None = None
        for coord in coords:
            value = coord & 0xFF
            index = value if index is None else self.values[index] ^ value
        assert index is not None
        return self.values[index]

    def hash3(self, x: int, y: int, z: int) -> int:
        values = self.values
        index = values[x & 0xFF] ^ (y & 0xFF)
        index = values[index] ^ (z & 0xFF)
        return values[index]


class OpenSimplex3:
    def __init__(self, seed: int) -> None:
        self.perm = PermutationTable(seed & U32_MASK)

    def get(self, x: float, y: float, z: float) -> float:
        stretch_constant = -1.0 / 6.0
        squish_constant = 1.0 / 3.0
        stretch_offset = (x + y + z) * stretch_constant
        sx = x + stretch_offset
        sy = y + stretch_offset
        sz = z + stretch_offset
        sfx = _noise_floor_to_isize(sx)
        sfy = _noise_floor_to_isize(sy)
        sfz = _noise_floor_to_isize(sz)
        squish_offset = (sfx + sfy + sfz) * squish_constant
        ox = sfx + squish_offset
        oy = sfy + squish_offset
        oz = sfz + squish_offset
        rx = sx - sfx
        ry = sy - sfy
        rz = sz - sfz
        region_sum = rx + ry + rz
        rpx = x - ox
        rpy = y - oy
        rpz = z - oz

        def contribute(dx: int, dy: int, dz: int) -> float:
            offset_sum = dx + dy + dz
            px = rpx - squish_constant * offset_sum - dx
            py = rpy - squish_constant * offset_sum - dy
            pz = rpz - squish_constant * offset_sum - dz
            t = 2.0 - (px * px + py * py + pz * pz)
            if t <= 0.0:
                return 0.0
            grad = GRAD3[self.perm.hash3(sfx + dx, sfy + dy, sfz + dz) % 32]
            return (t**4) * (px * grad[0] + py * grad[1] + pz * grad[2])

        if region_sum <= 1.0:
            value = contribute(0, 0, 0) + contribute(1, 0, 0) + contribute(0, 1, 0) + contribute(0, 0, 1)
        elif region_sum >= 2.0:
            value = contribute(1, 1, 0) + contribute(1, 0, 1) + contribute(0, 1, 1) + contribute(1, 1, 1)
        else:
            value = (
                contribute(1, 0, 0)
                + contribute(0, 1, 0)
                + contribute(0, 0, 1)
                + contribute(1, 1, 0)
                + contribute(1, 0, 1)
                + contribute(0, 1, 1)
            )
        return value / 14.0


def generate_world(resolved: Any) -> GeneratedWorld:
    rng = ChaCha8Rng(int(resolved.seed))
    simplex = OpenSimplex3(int(resolved.seed))
    width = int(resolved.width)
    height = int(resolved.height)
    player_pos = (width // 2, height // 2)
    densities = dict(resolved.substrate_config)
    runtime_mobs_enabled = bool(densities.get("mobs_enabled", True))
    if not runtime_mobs_enabled:
        densities["cow_density"] = 0.0
        densities["zombie_density"] = 0.0
        densities["skeleton_density"] = 0.0
    tiles = [["grass" for _ in range(width)] for _ in range(height)]
    tunnels = [[False for _ in range(height)] for _ in range(width)]
    for y in range(height):
        for x in range(width):
            material, tunnel = _terrain_material(
                float(x),
                float(y),
                player_pos,
                simplex,
                rng,
                densities,
            )
            tiles[y][x] = material
            tunnels[x][y] = tunnel
    entities = _spawn_classic_entities(tiles, tunnels, player_pos, rng, densities)
    if resolved.substrate_profile == "craftax_partial":
        craftax_config = dict(resolved.rules.get("craftax", {}))
        if craftax_config.get("enabled", True) and craftax_config.get("worldgen_enabled", True):
            _apply_craftax_worldgen(tiles, tunnels, entities, player_pos, rng, craftax_config, runtime_mobs_enabled)
    return GeneratedWorld(tiles=tiles, entities=entities, tunnels=tunnels, rng=rng)


def _terrain_material(
    x: float,
    y: float,
    player_pos: tuple[int, int],
    simplex: OpenSimplex3,
    rng: ChaCha8Rng,
    densities: dict[str, Any],
) -> tuple[str, bool]:
    px, py = float(player_pos[0]), float(player_pos[1])
    dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
    start = 4.0 - dist
    start += 2.0 * _simplex3_single(simplex, x, y, 8.0, 3.0)
    start = 1.0 / (1.0 + math.exp(-start))
    water = _simplex3(simplex, x, y, 3.0, ((15.0, 1.0), (5.0, 0.15)), normalize=False) + 0.1
    water -= 2.0 * start
    mountain = _simplex3(simplex, x, y, 0.0, ((15.0, 1.0), (5.0, 0.3)), normalize=True)
    mountain -= 4.0 * start + 0.3 * water
    if start > 0.5:
        return "grass", False
    if mountain > 0.15:
        return _mountain_material(x, y, mountain, simplex, rng, densities)
    if water > 0.25 and water <= 0.35 and _simplex3_single(simplex, x, y, 4.0, 9.0) > -0.2:
        return "sand", False
    if water > 0.3:
        return "water", False
    return _grassland_material(x, y, simplex, rng, densities), False


def _mountain_material(
    x: float,
    y: float,
    mountain: float,
    simplex: OpenSimplex3,
    rng: ChaCha8Rng,
    densities: dict[str, Any],
) -> tuple[str, bool]:
    if _simplex3_single(simplex, x, y, 6.0, 7.0) > 0.15 and mountain > 0.3:
        return "path", False
    if _simplex3_single(simplex, 2.0 * x, y / 5.0, 7.0, 3.0) > 0.4:
        return "path", True
    if _simplex3_single(simplex, x / 5.0, 2.0 * y, 7.0, 3.0) > 0.4:
        return "path", True
    if _simplex3_single(simplex, x, y, 1.0, 8.0) > 0.0 and rng.random_f64() > _scaled_threshold(0.30, densities.get("coal_density", 1.0)):
        return "coal", False
    if _simplex3_single(simplex, x, y, 2.0, 6.0) > 0.3 and rng.random_f64() > _scaled_threshold(0.30, densities.get("iron_density", 1.0)):
        return "iron", False
    if mountain > 0.18 and rng.random_f64() > _scaled_threshold(0.016, densities.get("diamond_density", 1.0)):
        return "diamond", False
    if mountain > 0.3 and _simplex3_single(simplex, x, y, 6.0, 5.0) > 0.35:
        return "lava", False
    return "stone", False


def _grassland_material(
    x: float,
    y: float,
    simplex: OpenSimplex3,
    rng: ChaCha8Rng,
    densities: dict[str, Any],
) -> str:
    if _simplex3_single(simplex, x, y, 5.0, 7.0) > 0.0 and rng.random_f64() > _scaled_threshold(0.2, densities.get("tree_density", 1.0)):
        return "tree"
    return "grass"


def _spawn_classic_entities(
    tiles: list[list[str]],
    tunnels: list[list[bool]],
    player_pos: tuple[int, int],
    rng: ChaCha8Rng,
    densities: dict[str, Any],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = {player_pos}
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    for y in range(height):
        for x in range(width):
            pos = (x, y)
            tile = tiles[y][x]
            if tile not in {"grass", "path", "sand", "lava"}:
                continue
            dist_sq = (x - player_pos[0]) ** 2 + (y - player_pos[1]) ** 2
            if tile == "grass" and dist_sq > 9 and rng.random_f64() > _scaled_threshold(0.015, densities.get("cow_density", 1.0)) and pos not in occupied:
                occupied.add(pos)
                entities.append(_entity("cow", pos, 3, len(entities)))
            if dist_sq > 100 and rng.random_f64() > _scaled_threshold(0.007, densities.get("zombie_density", 1.0)) and pos not in occupied:
                occupied.add(pos)
                entities.append(_entity("zombie", pos, 5, len(entities)))
            if tile == "path" and tunnels[x][y] and rng.random_f64() > _scaled_threshold(0.05, densities.get("skeleton_density", 1.0)) and pos not in occupied:
                occupied.add(pos)
                entities.append(_entity("skeleton", pos, 3, len(entities)))
    return entities


def _apply_craftax_worldgen(
    tiles: list[list[str]],
    tunnels: list[list[bool]],
    entities: list[dict[str, Any]],
    player_pos: tuple[int, int],
    rng: ChaCha8Rng,
    craftax_config: dict[str, Any],
    runtime_mobs_enabled: bool,
) -> None:
    occupied = {tuple(entity["pos"]) for entity in entities}
    occupied.add(player_pos)
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    items_enabled = bool(craftax_config.get("items_enabled", True))
    chests_enabled = bool(craftax_config.get("chests_enabled", True))
    mobs_enabled = bool(craftax_config.get("mobs_enabled", True)) and runtime_mobs_enabled
    for y in range(height):
        for x in range(width):
            pos = (x, y)
            dist_sq = (x - player_pos[0]) ** 2 + (y - player_pos[1]) ** 2
            tile = tiles[y][x]
            if items_enabled and tile == "stone":
                if rng.random_f32() < 0.004:
                    tiles[y][x] = "sapphire"
                    continue
                if rng.random_f32() < 0.003:
                    tiles[y][x] = "ruby"
                    continue
            if items_enabled and chests_enabled and dist_sq > 36 and tile in {"grass", "path"} and rng.random_f32() < 0.002:
                tiles[y][x] = "chest"
                continue
            if not mobs_enabled:
                continue
            if tile == "grass" and dist_sq > 16 and rng.random_f32() < 0.01 and pos not in occupied:
                occupied.add(pos)
                entities.append(_entity("snail", pos, 3, len(entities)))
                continue
            if tile == "path" and tunnels[x][y] and rng.random_f32() < 0.02 and pos not in occupied:
                occupied.add(pos)
                entities.append(_entity("bat", pos, 2, len(entities)))
                continue
            if dist_sq > 100 and tile in {"grass", "path", "sand", "lava"} and pos not in occupied:
                for kind, prob, health in (
                    ("orc_soldier", 0.004, 5),
                    ("orc_mage", 0.003, 3),
                    ("knight", 0.003, 9),
                    ("knight_archer", 0.003, 8),
                ):
                    if rng.random_f32() < prob:
                        occupied.add(pos)
                        entities.append(_entity(kind, pos, health, len(entities)))
                        break
                else:
                    if tile == "lava" or rng.random_f32() < 0.002:
                        occupied.add(pos)
                        entities.append(_entity("troll", pos, 12, len(entities)))


def _simplex3(simplex: OpenSimplex3, x: float, y: float, z: float, sizes: tuple[tuple[float, float], ...], *, normalize: bool) -> float:
    value = 0.0
    total = 0.0
    for size, weight in sizes:
        value += weight * simplex.get(x / size, y / size, z)
        total += weight
    return value / total if normalize and total else value


def _simplex3_single(simplex: OpenSimplex3, x: float, y: float, z: float, size: float) -> float:
    return simplex.get(x / size, y / size, z)


def _scaled_threshold(base_probability: float, multiplier: Any) -> float:
    probability = min(base_probability * max(0.0, float(multiplier)), 1.0)
    return 1.0 - probability


def _entity(kind: str, pos: tuple[int, int], health: int, idx: int) -> dict[str, Any]:
    return {"id": f"world_{idx}", "kind": kind, "pos": [pos[0], pos[1]], "health": health, "metadata": {}}


def _gen_index_u32(rng: XorShiftRng, ubound: int) -> int:
    assert 0 < ubound <= U32_MASK
    return _sample_single_u32(rng, 0, ubound)


def _sample_single_u32(rng: Any, low: int, high: int) -> int:
    assert low < high
    range_value = int(high) - int(low)
    zone = ((range_value << (32 - range_value.bit_length())) - 1) & U32_MASK
    while True:
        value = rng.next_u32()
        product = value * range_value
        hi = (product >> 32) & U32_MASK
        lo = product & U32_MASK
        if lo <= zone:
            return int(low) + hi


def _read_u32_le(data: list[int] | bytes, offset: int) -> int:
    return int(data[offset]) | (int(data[offset + 1]) << 8) | (int(data[offset + 2]) << 16) | (int(data[offset + 3]) << 24)


def _noise_floor_to_isize(value: float) -> int:
    # Mirrors noise 0.9.0 Vector::floor_to_isize, including its <= 0 boundary behavior.
    return int(value) - 1 if value <= 0.0 else int(value)


def _chacha_seed_from_u64(seed: int) -> list[int]:
    state = seed & U64_MASK
    data: list[int] = []
    for _ in range(8):
        state = (state * 6364136223846793005 + 11634580027462260723) & U64_MASK
        xorshifted = (((state >> 18) ^ state) >> 27) & U32_MASK
        rot = (state >> 59) & 31
        value = _rotate_right_u32(xorshifted, rot)
        data.extend([value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF])
    key = [_read_u32_le(data, idx) for idx in range(0, 32, 4)]
    return [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574, *key, 0, 0, 0, 0]


def _chacha_double_round(state: list[int]) -> None:
    _quarter_round(state, 0, 4, 8, 12)
    _quarter_round(state, 1, 5, 9, 13)
    _quarter_round(state, 2, 6, 10, 14)
    _quarter_round(state, 3, 7, 11, 15)
    _quarter_round(state, 0, 5, 10, 15)
    _quarter_round(state, 1, 6, 11, 12)
    _quarter_round(state, 2, 7, 8, 13)
    _quarter_round(state, 3, 4, 9, 14)


def _quarter_round(state: list[int], a: int, b: int, c: int, d: int) -> None:
    state[a] = (state[a] + state[b]) & U32_MASK
    state[d] = _rotate_left_u32(state[d] ^ state[a], 16)
    state[c] = (state[c] + state[d]) & U32_MASK
    state[b] = _rotate_left_u32(state[b] ^ state[c], 12)
    state[a] = (state[a] + state[b]) & U32_MASK
    state[d] = _rotate_left_u32(state[d] ^ state[a], 8)
    state[c] = (state[c] + state[d]) & U32_MASK
    state[b] = _rotate_left_u32(state[b] ^ state[c], 7)


def _rotate_left_u32(value: int, bits: int) -> int:
    value &= U32_MASK
    return ((value << bits) | (value >> (32 - bits))) & U32_MASK


def _rotate_right_u32(value: int, bits: int) -> int:
    value &= U32_MASK
    return ((value >> bits) | (value << (32 - bits))) & U32_MASK
