# Brief — Juggle (motion and physics demo)

Engine demo for WP-09. Pip juggles a three-ball cascade, solved from the siteswap "3": every throw and catch lands on
the beat of the score (100 bpm, half-beat grid), the balls stretch along their flight, smear when fast and squash
when caught, and the motion arcs trail behind them. Then the juggle goes wrong: the balls carry on as Rapier bodies
(deterministic build), fall, bounce off the floor and knock two crates about, each big contact retimed onto the beat.

| field     | value |
|-----------|-------|
| audience  | internal (engine demo) |
| review    | standard |
