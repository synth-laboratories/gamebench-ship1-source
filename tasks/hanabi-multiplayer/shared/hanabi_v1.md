# Hanabi v1 rules contract

This task implements standard two-player Hanabi as a cooperative,
alternating-turn symbolic environment.

- The deck has five colors and ranks 1–5 with multiplicities 3, 2, 2, 2, 1.
- Each player holds five cards. A player sees the partner's cards but never
  their own card identities.
- The team starts with eight information tokens and three life tokens.
- A turn is exactly one `play`, `discard`, or `hint` action.
- A hint names one color or one rank and must match at least one partner card.
  It updates both positive and negative knowledge for every partner card.
- A successful play advances that color's firework. Playing a five restores
  one information token up to the cap.
- A misplay consumes one life and discards the card. A discard restores one
  information token and is illegal while tokens are full.
- Drawing the final deck card starts a two-turn countdown after the current
  turn. The game also ends on zero lives or a perfect score of 25.

The authoritative state contains card identities. Observations replace every
own card identity with `null` and expose only accumulated hint knowledge.
Checkpoints may contain authority state and must not be passed to policies.
