# Гексагональний атлас — v01

`terrain_hex_v01.png` — візуальна чернетка для узгодження стилю майбутньої
гексагональної світової мапи. 1448 × 1086 px, RGBA, прозоре тло.
48 тайлів: 8 колонок × 6 рядів, вершина гекса вгорі.

Ряди зверху вниз:

1. Пустки: ґрунт, тріщини, гравій, суха рослинність, дрібні уламки.
2. Ліси: сухі дерева, рідкі та густі крони, галявини, вигорілий ліс.
3. Руїни, поселення, місто, бункер і службова територія.
4. Вода та шість варіантів узбережжя.
5. Каміння, скелі, валуни, гряди та осипи.
6. Асфальтові дороги: прямі, повороти та перехрестя.

**Радіаційних тайлів немає.** Радіація має відображатися окремим ігровим
накладеним ефектом поверх звичайної місцевості.

Референс стилю: наявний `assets/terrain_source.png`. Збережено приглушену
постапокаліптичну палітру, вигляд згори та матеріали поточних локацій.

Це ще не технічний атлас для автоматичної нарізки: генератор не витримав
ідеально рівномірну сітку, зокрема висоту нижнього ряду. Перед інтеграцією
потрібно уніфікувати маски, відступи та точки стикування доріг, визначити
потрібний набір з'єднань і створити точні координати клітинок.
У цьому варіанті немає повного набору дорожніх масок чи всіх переходів біомів.

Атлас не підключений до гри. Код, поточні атласи та збереження не змінені.
Робоча гілка: `feature-2-hexagon-map`, яка вже була активна на початку роботи.

## Генерація

Використано вбудований інструмент ImageGen (навичка imagegen), не CLI/API.
Нижче фінальний промпт корекції; початковим референсом слугував поточний атлас,
а референсом корекції — перша згенерована версія. Не всі геометричні вимоги
промпту виконані генератором; обмеження зазначені вище.

```text
Edit this atlas to fix ONLY geometry and spacing, preserving the 48 terrain artworks and their exact 8 columns by 6 rows ordering, palette and detailed post-apocalyptic overhead style. CRITICAL: all 48 hexagons including the eight ROAD hexagons on the bottom row must be IDENTICAL REGULAR POINTY TOP HEXAGONS. The supplied bottom road row is wrongly compressed vertically: rebuild those road tiles to be full height, exactly as tall as every terrain tile. Use a strict rectangular 8x6 grid of equally sized SQUARE cells with centers equally spaced horizontally and vertically. Each regular hexagon must have height exactly 80% of its square cell and width exactly 69.28% of its square cell. This gives generous TRANSPARENT gutters around EVERY tile, including the top, bottom and sides. Do not enlarge hexagons to touch each other. No thin stray connecting bands between tiles. No extruded sides or isometric perspective, no outlines, no text. Entire image has real transparent alpha outside the tiles, no opaque black background. All top vertices and bottom vertices centered in their cells. Every road meets center of appropriate hexagon edge, not a vertex: bottom row E-W straight, NE-SW straight, NW-SE straight, bend E-NE, bend E-NW, T-junction W-E-NE, Y-junction W-NE-SE, finally SIX-way junction connecting all SIX hexagon EDGE midpoints (not an ordinary square four-way crossing). Maintain same road width. No radiation variants, toxic pools or green glow anywhere. Leave first five rows' artwork content as close to input as possible, merely resize and reposition into equal regular hex masks. Final deliverable is a single neatly spaced 8x6 transparent PNG spritesheet, landscape 4:3.
```
