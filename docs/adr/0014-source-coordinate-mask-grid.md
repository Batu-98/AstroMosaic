# ADR-0014 - Store editable content masks on a bounded source grid

- **Date:** 2026-11-16
- **Status:** Accepted for Phase 3D.

Store sky, foreground, and unclassified cells together. Divide each source axis at integer pixel edges and assign every source pixel to one cell. Cap the longest side of the editable grid at 384 cells. Sample content selection by source tile and intersect the selected label with the source validity. This gives future ground processing the same selection geometry as sky processing.

Run the foreground check on a bounded 128-cell thumbnail. Use a separate cancellable job on the 384-cell grid for mask proposals. The local detector looks for a bottom-attached horizon with a supported step across adjacent columns. Proposals retain an unclassified strip and leave unsupported columns unclassified. Users can override any tag, trace a horizon, and paint all three labels.

Version 2 project manifests save the suggestion, override, and edited grid with the source reference. Version 1 projects and attached binary FITS masks still load. An authored mask binds a solved WCS to the selected sky cells by SHA-256. A change from foreground to unclassified leaves the hash unchanged because both labels exclude the cell from sky processing.

[Workflow and verification](../phase-3d.md)
