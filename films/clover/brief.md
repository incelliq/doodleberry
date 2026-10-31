# Brief — "Why farmers rotate clover"

Original film. Built to prove out a reusable code engine for the
"cartoon cross-section explainer" genre (side-view soil cutaway, prop
characters with faces, translucent underground callouts, one-word kinetic
captions, narration-led). A reference reel of that genre was studied for
pacing and devices only; no footage, characters, layouts, script or music
were copied, and the subject is different.

| field      | value | why |
|------------|-------|-----|
| mode       | explainer | one cause and effect: rhizobia fix nitrogen → clover feeds the next crop |
| subject    | legume nitrogen fixation in crop rotation | a mechanism that lives underground, so it exercises the cutaway + macro-callout devices |
| viewer     | curious feed scroller, gardeners, students | they care about "why do farmers do that?" |
| end state  | know: clover fertilizes the soil for the next crop | single takeaway, said and shown |
| length     | ~32 s, 9:16 (1080×1920) | genre is vertical short-form |
| frame rate | 30 | character animation |
| brand      | none — own palette, Fredoka (OFL) | no client brand |
| facts      | facts.json (Wikipedia "Nitrogen fixation") | only source for claims |
| assets     | everything drawn in SVG code | no raster assets |
| style      | flat cel cartoon, warm ink outline, soft sky | genre convention, own palette |
| sound      | voice + music + sfx; baby-voiced narrator | narration-led genre; baby voice requested by the user after delivery |
| autonomy   | unattended | user is away; gates logged in ledger.md instead of stopping |
| toolchain  | HTML/SVG + own frame-function timeline, Playwright, ffmpeg | every value is a function of frame number; no runtime deps |
| sign-off   | end title "Clover: it feeds the next crop." + source line | recap + attribution |
