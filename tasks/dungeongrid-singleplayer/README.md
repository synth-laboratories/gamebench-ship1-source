# DungeonGrid Singleplayer

This task is the one-controller DungeonGrid contract. The policy exclusively
controls `hero_0` in the `barbarian` role through the active-agent action API.
It has its own task identity, scenarios, policy suite, and Python authority; it
does not dispatch to the multiplayer task at runtime.

Run the trusted policy sweep with:

`python scripts/run_hillclimb.py --output /tmp/dungeongrid-singleplayer`
