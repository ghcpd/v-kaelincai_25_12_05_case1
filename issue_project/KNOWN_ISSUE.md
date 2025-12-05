# Known Issue: Dijkstra on Negative Weights

**Type:** Missing input validation / incorrect algorithm choice

**Symptom:** `dijkstra_shortest_path` returns the non-optimal route `A→B` (cost 5) instead of `A→C→D→F→B` (cost 1) because it runs Dijkstra on a graph containing a negative edge `D→F = -3`.

**Root Cause:**
- No validation rejects graphs with negative weights before invoking Dijkstra.
- Implementation marks nodes as visited upon discovery, preventing later relaxations that would yield a cheaper path.

**Trigger:** Load `data/graph_negative_weight.json` and route `A` to `B`.

**Expected Behavior:**
- Either raise an error when negative weights are present, **or** use Bellman-Ford (or another algorithm supporting negative edges) to compute the correct shortest path (total cost 1).

**Fix Ideas (not implemented):**
- Scan edges for `weight < 0` before running Dijkstra; raise `ValueError` or switch algorithms.
- Correct the Dijkstra implementation to mark nodes visited when popped (finalized), not when first discovered.
- Provide a Bellman-Ford implementation for graphs with negative weights.
