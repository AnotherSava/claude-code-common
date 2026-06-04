# build123d/OCCT fillet robustness: convexity, concave space requirements, and move-poisoning

Findings from building a genderless dovetail "puzzle" connector (cable channel, R0.7 fillets) in the build123d-models project. See `cablechannel.py::_create_lock_plate` for the working pattern.

## Fuse first, then fillet — OCCT resolves convexity per edge

To round a bump's *external* (tip) corners outward AND its *internal* (root, where it meets the body) corners inward — the way a 2D draft filleter does — fuse the bump onto its slab/body **first**, then fillet the vertical edges. OCCT rounds each edge according to its own convexity: convex edges → outward (material removed), concave edges → inward (blend material added).

A standalone box filleted *before* fusing rounds **all four** corners outward; after fusing, the root junction stays a sharp concave crease, and the part visibly mismatches a draft whose internal corners curve inward.

```python
plate = slab.fuse(bump)                    # junction edges now exist and are concave
edges = filter_edges_by_axis(plate.solid.edges(), Axis.Z)
tip   = filter_edges_by_position(edges, Axis.X, tip_x - 0.1, tip_x + 0.1, (True, True))
root  = filter_edges_by_position(edges, Axis.X, root_x - 0.1, root_x + 0.1, (True, True))
root  = filter_edges_by_position(root, Axis.Y, yc - root_half - 0.2, yc + root_half + 0.2, (True, True))
plate.solid = fillet(list(tip) + list(root), radius)
```

## A concave fillet needs ≥ radius of flat face beyond the corner

A concave (internal) fillet blends into the adjoining flat face. If that face extends *less than the fillet radius* past the edge (e.g. a flange only 0.5 mm wider than the bump for an R0.7 fillet), the fillet fails at **every** radius down to tiny values — not just at the requested one. Widen the slab/flange so the margin beyond the bump root is comfortably ≥ R.

## Fillet the small sub-assembly, not the full model

Filleting the bump junction edges directly on the assembled channel — where the end face is a complex meeting of floor, walls, and rim — failed outright at all radii. The same edges fillet fine on the isolated slab+bump sub-assembly. Pattern: build the local feature as its own small solid, fillet it there, then fuse the finished piece onto the model.

## Sacrificial flange for cut features (sockets)

A cut pocket can't get a convex mouth from a convex-cornered cutter (cutting inverts convexity: cutter-convex → pocket-concave and vice versa). Give the cutter a sacrificial flange sitting in **empty space** just outboard of the cut: the flange gives the cutter's bump a concave root, so after the cut the pocket's mouth rounds convex and its interior concave — the exact complement of the mating tab. The flange itself removes nothing because it occupies empty space.

## Move-before-fillet can poison the geometry (mixed evidence — not yet a hard rule)

In this session, the identical slab+bump plate filleted fine at the origin but failed at every radius after being aligned to the channel (x≈30); per the project's earlier measurement, replaying a SmartSolid orientation transform during `move`/`align` lands faces ~1e-7 off, and that sliver breaks the fillet. Filleting at the origin and moving the finished solid afterwards fixed it deterministically.

**Caveat:** this is one clean negative example, but there were positive examples too — other rotated-then-moved solids filleted fine in earlier sessions, and in one integration run the tab plate filleted after placement while only the socket failed. Worth keeping in mind as the first suspect when a fillet "mysteriously" fails after a move (especially when each edge fillets alone but the set fails together), but it needs more data before being stated as a rule.

## Diagnostic ladder for a failing fillet

1. Fillet each candidate edge **individually** — if every edge succeeds alone but the set fails together, suspect poisoned coordinates (see above) or fillets needing more room than the shared faces allow.
2. Reduce the radius stepwise — failure at *all* radii points to topology/space problems (concave margin, complex adjacent faces), not an oversized radius.
3. Rebuild the same shape at the origin and retry — isolates transform-error effects from genuine geometry limits.
4. List the matched edges' centers (`edge.center()`) before filleting — selection bugs (extra slab corners, off-by-`root_half` Y windows) look identical to OCCT failures otherwise.
