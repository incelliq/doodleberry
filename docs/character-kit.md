# Making a character with an image model (for cast.from_kit)

Studios design a character on a model sheet first and draw the rig's parts for the rig. Do the same with an image
model: one chat per character, attaching the previous step's picture to each new step so the pictures stay
consistent. Then build the puppet:

```
python -m dbe cast.from_kit '{"kit": "...kit.jpg", "sheet": "...turnaround.jpg", "mouths": "...mouths.jpg",
  "name": "Nila", "model": "<image model>", "license": "<its licence>", "out": "out/fromsheet/nila.puppet.json"}'
```

Keep the pictures and puppets out of git until the image model's licence is recorded (the repo ignores `tmp/` and
`out/`). Check every character for resemblance to existing ones.

## 1. Model sheet (turnaround)
```
Character turnaround model sheet of <NAME>, an original cartoon character: <DESCRIPTION>. Four full-body views side by
side at the same height and scale: front, three-quarter, side (facing right), back. Standing relaxed, arms down.
Style: flat 2D cartoon, clean dark brown outlines of even thickness, flat colours with no gradients, shading, texture
or shadows, on a pure white background. No ground, no labels, no text.
```
Leave bags and other props out: they become props.

## 2. Cut-out kit (attach the model sheet)
```
Using the attached character exactly (same face, hair, clothes, colours, flat style and dark brown outlines), draw
<them> as a cut-out puppet kit for 2D animation, front view, on a pure white background. Draw each part separately, all
at the same scale as the attached picture, spaced well apart so no two parts touch. Draw every part complete, including
the areas another part would normally cover:
1. Head with hair, ears and face (eyes open, small closed smile), ending at the jaw. No neck.
2. Torso: the top's body only, with the neck rising out of the collar, long enough to tuck up under the chin. No head
   and no arms: the shoulders are rounded and closed where the sleeves would be. No sleeves on the torso.
3. Hips: the shorts (or trousers, or skirt) only, no legs.
4. and 5. Right arm and left arm: each straight and hanging down, whole from a fully rounded shoulder end with its
   sleeve down to a relaxed open hand.
6. and 7. Right leg and left leg: each straight, whole from a rounded top of the thigh down to the shoe.
Layout: head, torso and hips in the top row, left to right; the two arms then the two legs in the bottom row. No
shadows, no ground, no labels, no text.
```
For an ankle-length skirt or sari: the hips are the skirt from the waist to the ankles, and 6 and 7 are each foot in
its shoe with a short piece of ankle with a rounded top.

Check before saving: no two parts touch; 3 pieces on top and 4 below; limbs straight and whole; plain white. Models
often draw sleeves on the torso, a neck on the head, or the whole figure as the torso: ask for an edit, for example

```
Edit the attached kit. Change only the torso piece (top middle): remove its sleeves so it is the top's body only, with
rounded, closed shoulders (the sleeves are already on the arm pieces), and make the neck the same skin colour as the
face and arms. Keep every other piece exactly as it is, in the same place.
```
```
Edit the attached kit. Change only the middle piece of the top row: it must be the torso alone, from the neckline down
to the waist, with the neck rising out of the neckline. Remove the head from it (the head is the first piece) and the
skirt below the waist (the skirt is the third piece), and draw no sleeves on it. Also remove the neck from the head
piece, so the head ends at the jaw. Keep every other piece exactly as it is, in the same place.
```
`cast.from_kit` warns about the first two in its result.

## 3. Mouths (attach the model sheet)
```
Six cartoon mouths for the attached character, drawn alone on a pure white background, in one row, same flat style
and dark brown outlines: 1 closed smile (a single line, like the face's own smile), 2 slightly open, 3 wide open "ah",
4 round "oh", 5 wide "ee" showing the top teeth, 6 tongue touching the top teeth "l". No full lip shapes, no face, no
text.
```

## Later sheets
Hand poses (open, fist, point, wave, hold) and the head at three-quarter and in profile, for drawing swaps and turns.
