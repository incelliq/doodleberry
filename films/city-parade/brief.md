# Brief — City parade (procedural and 3D layer demo)

Engine demo for WP-42. One shot mixes three layers under one camera (a slow push in): a city built with Blender
Geometry Nodes (a scatter of blocks with random sizes and shades, cel-shaded with ink lines) rendered by a camera
derived from the shot's 2D camera keys; a procedural crowd (a seeded scatter, cast members on depth planes standing on the
3D ground, idles out of phase, cheers at seeded times); and Pip, a 2D puppet, on the stage. Confetti falls on the
cheer. The graph is cached node by node, so a change to the crowd re-cooks the crowd and not the city.

| field     | value |
|-----------|-------|
| audience  | internal (engine demo) |
| review    | standard |
