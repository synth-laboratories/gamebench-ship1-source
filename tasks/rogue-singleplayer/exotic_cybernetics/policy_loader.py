"""Policy loading for rogue-singleplayer exotic cybernetics."""

from shared.exotic_cybernetics.policy_loader import load_cybernetics_policy, policy_sha256

from exotic_cybernetics.config import MODULE_PREFIX, POLICY_ENTRY

__all__ = ["load_cybernetics_policy", "policy_sha256"]


def load_env_cybernetics_policy(policy_path, *, steer_session=None):
    return load_cybernetics_policy(
        policy_path,
        steer_session=steer_session,
        entry=POLICY_ENTRY,
        module_prefix=MODULE_PREFIX,
    )
