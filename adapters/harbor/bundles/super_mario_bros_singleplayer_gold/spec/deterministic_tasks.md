# Deterministic task rules

The complete deterministic input is `(level_id, seed, ordered action tape)`.
The engine uses integer fixed-point arithmetic, no wall clock, and no ambient
random number generator. Restoring a checkpoint and replaying a tape must
produce identical state, semantic events, score, progress, and RGB bytes.

Rollout handles and checkpoint IDs are HTTP bookkeeping and are not compared.
Terminal reasons are explicit: `completed`, `death`, and `timeout`. Steps after
termination are no-ops.
