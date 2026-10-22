"""Genera i tre set di icone di fili (SVG) e le tavole di anteprima.  Uso:  python assets/icons/build_icons.py

Una sola geometria (griglia 24 px), tre trattamenti grafici:
  set-1-filo     contorno sottile blu notte con un tratto "filo" azzurro
  set-2-duotone  contorno piu' marcato con riempimento azzurro tenue sulle forme chiuse
  set-3-badge    glifo bianco su tessera colorata per categoria
Ogni cartella contiene anche app-icon.svg (512 px), diversa per ciascun set.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INK, ACC = "#1B2A41", "#0E9AA7"

# ruolo: i = contorno, a = tratto "filo"; il terzo valore (True) marca le forme chiuse che il duotone puo' riempire
ICONS = {
    "usb-device": ("Device", "info", [
        ("a", '<path d="M12 16.6V4.4"/>', False),
        ("i", '<path d="M9.3 7L12 3.7 14.7 7"/>', False),
        ("i", '<path d="M12 14.4l-5.2-3V9.4M12 11.6l5-2.8V7.2"/>', False),
        ("i", '<circle cx="6.8" cy="7.4" r="1.8"/><rect x="15.2" y="4.4" width="3.6" height="3" rx=".7"/>', True),
        ("i", '<circle cx="12" cy="19" r="2.2"/>', True),
    ]),
    "install": ("Install", "action", [
        ("i", '<rect x="4.5" y="4.5" width="15" height="15" rx="3.2"/>', True),
        ("a", '<path d="M12 8.2v6.4M9.2 12l2.8 2.8 2.8-2.8"/>', False),
    ]),
    "reinstall": ("Reinstall", "action", [
        ("i", '<path d="M19.6 11.2A7.6 7.6 0 0 0 6.1 7.2L4.6 8.8"/><path d="M4.4 12.8a7.6 7.6 0 0 0 13.5 4l1.5-1.6"/>', False),
        ("a", '<path d="M4.6 4.4v4.5h4.5M19.4 19.6v-4.5h-4.5"/>', False),
    ]),
    "restore": ("Restore", "action", [
        ("i", '<path d="M4.4 12a7.6 7.6 0 1 1 2.4 5.6"/><path d="M12 7.8v4.4l2.8 1.7"/>', False),
        ("a", '<path d="M4.4 5.8V12h6.2"/>', False),
    ]),
    "diagnose": ("Diagnose", "info", [
        ("i", '<circle cx="10.4" cy="10.4" r="6.6"/><path d="M15.4 15.4L20 20"/>', True),
        ("a", '<path d="M6.6 10.6h2l1.2-2.6 1.8 5 1.2-2.4h1"/>', False),
    ]),
    "certificates": ("Certificates", "info", [
        ("i", '<rect x="3.5" y="3.5" width="17" height="14" rx="2.2"/><path d="M15.2 17.5l-.2 3 1.8-1.1 1.8 1.1-.2-3"/>', True),
        ("a", '<path d="M7 8h6M7 11.5h3"/><circle cx="16.8" cy="11.6" r="2.3"/>', False),
    ]),
    "licenses": ("Licenses", "info", [
        ("i", '<path d="M7 3h7.2L19 7.8V19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M14 3v5h5"/>', True),
        ("a", '<path d="M8.6 13h6.8M8.6 16.6h4.4"/>', False),
    ]),
    "save": ("Save output", "neutral", [
        ("i", '<path d="M4.8 14.6v3.6a2 2 0 0 0 2 2h10.4a2 2 0 0 0 2-2v-3.6"/>', False),
        ("a", '<path d="M12 3.8v10.2M8 10.4l4 3.8 4-3.8"/>', False),
    ]),
    "refresh": ("Refresh", "action", [
        ("i", '<path d="M19.6 12a7.6 7.6 0 1 1-2.3-5.4"/>', False),
        ("a", '<path d="M19.6 4.4v4.6h-4.6"/>', False),
    ]),
    "help": ("Help", "info", [
        ("i", '<circle cx="12" cy="12" r="9"/>', True),
        ("a", '<path d="M9.4 9.5a2.7 2.7 0 1 1 3.9 2.4c-.8.4-1.3 1-1.3 1.9M12 17.3h.01"/>', False),
    ]),
    "about": ("About", "info", [
        ("i", '<circle cx="12" cy="12" r="9"/>', True),
        ("a", '<path d="M12 11v5.4M12 7.7h.01"/>', False),
    ]),
    "support": ("Ko-fi", "neutral", [
        ("i", '<path d="M4.8 8.8h11v5.2a4.4 4.4 0 0 1-4.4 4.4H9.2a4.4 4.4 0 0 1-4.4-4.4z"/><path d="M15.8 10h1.2a2.5 2.5 0 0 1 0 5h-1.2M4 20.8h12.6"/>', True),
        ("a", '<path d="M8.2 3.2v2.4M11.6 3.2v2.4"/>', False),
    ]),
    "usb-reset": ("USB reset", "action", [
        ("i", '<path d="M7.2 6.4a8 8 0 1 0 9.6 0"/>', False),
        ("a", '<path d="M12 3v8.2"/>', False),
    ]),
    "hubs": ("Show hubs", "info", [
        ("i", '<path d="M12 8.6V12M5 16v-2.2a1.8 1.8 0 0 1 1.8-1.8h10.4a1.8 1.8 0 0 1 1.8 1.8V16"/>', False),
        ("i", '<rect x="3" y="16" width="4" height="4" rx="1"/><rect x="10" y="16" width="4" height="4" rx="1"/><rect x="17" y="16" width="4" height="4" rx="1"/>', True),
        ("a", '<rect x="9" y="3.4" width="6" height="5.2" rx="1.3"/>', False),
    ]),
    "admin": ("Administrator", "warn", [
        ("i", '<path d="M12 3l7.2 3v5.5c0 4.2-3 7.6-7.2 9.5-4.2-1.9-7.2-5.3-7.2-9.5V6z"/>', True),
        ("a", '<path d="M8.9 12l2.3 2.3 3.9-4.5"/>', False),
    ]),
    "force": ("Force", "warn", [
        ("i", '<path d="M12 3.8l9.2 16H2.8z"/>', True),
        ("a", '<path d="M12 10v4.2M12 17.2h.01"/>', False),
    ]),
    "twins": ("All matching", "action", [
        ("i", '<rect x="3" y="5.5" width="11.2" height="11.2" rx="2.6"/>', True),
        ("a", '<rect x="9.8" y="8.4" width="11.2" height="11.2" rx="2.6"/>', False),
    ]),
    "filter": ("Filter driver", "action", [
        ("i", '<path d="M3.8 4.8h16.4l-6.3 7.5V19l-3.8 2v-8.7z"/>', True),
        ("a", '<path d="M8 8.2h8"/>', False),
    ]),
}

TILE = {"action": "#0E9AA7", "info": "#2F5DA8", "neutral": "#4B5B73", "warn": "#B86A00"}


def glyph(parts, ink, acc, sw, tint=None, acc_opacity=1.0):
    out = []
    for role, svg, closed in parts:
        stroke = ink if role == "i" else acc
        extra = ""
        if tint and closed:
            extra = ' fill="%s" fill-opacity="%s"' % tint
        op = ' stroke-opacity="%s"' % acc_opacity if (role == "a" and acc_opacity < 1) else ""
        out.append('<g stroke="%s"%s%s>%s</g>' % (stroke, op, extra, svg))
    head = 'fill="none" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"' % sw
    return head, "".join(out)


def icon_svg(style, parts, cat):
    if style == 1:
        head, body = glyph(parts, INK, ACC, 1.6)
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" %s>%s</svg>\n' % (head, body)
    if style == 2:
        head, body = glyph(parts, INK, ACC, 1.9, tint=(ACC, "0.2"))
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" %s>%s</svg>\n' % (head, body)
    head, body = glyph(parts, "#FFFFFF", "#FFFFFF", 1.8, acc_opacity=0.72)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
            '<rect width="32" height="32" rx="8" fill="%s"/><g transform="translate(4 4)" %s>%s</g></svg>\n') % (TILE[cat], head, body)


APP = {
    1: '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
<rect width="512" height="512" rx="112" fill="#14233A"/>
<g fill="none" stroke-linecap="round" stroke-linejoin="round">
<path d="M256 372V150" stroke="#2CC4CF" stroke-width="24"/>
<path d="M214 192L256 128l42 64" stroke="#FFFFFF" stroke-width="24"/>
<path d="M256 300L168 248v-42" stroke="#FFFFFF" stroke-width="24"/>
<path d="M256 262l88-52v-34" stroke="#FFFFFF" stroke-width="24"/>
</g>
<circle cx="168" cy="178" r="26" fill="#FFFFFF"/>
<rect x="318" y="126" width="52" height="46" rx="9" fill="#FFFFFF"/>
<circle cx="256" cy="392" r="38" fill="#FFFFFF"/>
<path d="M256 430c0 40-40 46-62 62" fill="none" stroke="#2CC4CF" stroke-width="16" stroke-linecap="round"/>
</svg>
''',
    2: '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
<rect width="512" height="512" rx="112" fill="#0E9AA7"/>
<rect x="96" y="110" width="320" height="156" rx="78" fill="#FFFFFF"/>
<rect x="150" y="170" width="212" height="36" rx="18" fill="#14233A"/>
<g fill="none" stroke="#FFFFFF" stroke-width="22" stroke-linecap="round" stroke-linejoin="round">
<path d="M130 336h250M346 300l36 36-36 36"/>
<path d="M382 412H132M166 376l-36 36 36 36"/>
</g>
</svg>
''',
    3: '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
<rect width="512" height="512" rx="112" fill="#14233A"/>
<g fill="#B8C4D4">
<rect x="150" y="84" width="22" height="50" rx="8"/><rect x="214" y="84" width="22" height="50" rx="8"/><rect x="278" y="84" width="22" height="50" rx="8"/><rect x="342" y="84" width="22" height="50" rx="8"/>
<rect x="150" y="378" width="22" height="50" rx="8"/><rect x="214" y="378" width="22" height="50" rx="8"/><rect x="278" y="378" width="22" height="50" rx="8"/><rect x="342" y="378" width="22" height="50" rx="8"/>
<rect x="84" y="150" width="50" height="22" rx="8"/><rect x="84" y="214" width="50" height="22" rx="8"/><rect x="84" y="278" width="50" height="22" rx="8"/><rect x="84" y="342" width="50" height="22" rx="8"/>
<rect x="378" y="150" width="50" height="22" rx="8"/><rect x="378" y="214" width="50" height="22" rx="8"/><rect x="378" y="278" width="50" height="22" rx="8"/><rect x="378" y="342" width="50" height="22" rx="8"/>
</g>
<rect x="124" y="124" width="264" height="264" rx="46" fill="#FFFFFF"/>
<circle cx="256" cy="256" r="84" fill="#0E9AA7"/>
<g fill="none" stroke="#FFFFFF" stroke-width="18" stroke-linecap="round" stroke-linejoin="round">
<path d="M204 240a56 56 0 0 1 98-22"/><path d="M308 190v32h-32"/>
<path d="M308 272a56 56 0 0 1-98 22"/><path d="M204 322v-32h32"/>
</g>
</svg>
''',
}
NAMES = {1: "set-1-filo", 2: "set-2-duotone", 3: "set-3-badge"}
TITLES = {1: "Set 1 - Filo (contorno sottile)", 2: "Set 2 - Duotone (contorno e riempimento)", 3: "Set 3 - Badge (tessera colorata)"}


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def preview(style):
    d = os.path.join(HERE, NAMES[style])
    cells = []
    for name, (label, cat, parts) in ICONS.items():
        svg = icon_svg(style, parts, cat)
        small = svg.replace('width="24" height="24"', 'width="16" height="16"').replace('width="32" height="32"', 'width="16" height="16"')
        big = svg.replace('width="24" height="24"', 'width="44" height="44"').replace('width="32" height="32"', 'width="44" height="44"')
        cells.append('<div class="c">%s<div class="s">%s</div><b>%s</b></div>' % (big, small, label))
    app = APP[style].replace('width="512" height="512"', 'width="160" height="160"', 1)
    app_s = APP[style].replace('width="512" height="512"', 'width="48" height="48"', 1)
    app_x = APP[style].replace('width="512" height="512"', 'width="24" height="24"', 1)
    page = ('<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#F2F5F8;font:13px "Segoe UI",sans-serif;color:#1B2A41;padding:24px;width:1000px}'
            'h1{font-size:18px;margin:0 0 14px}.g{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}.c{background:#fff;border:1px solid #D9E0E8;'
            'border-radius:10px;height:96px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;position:relative}'
            '.s{position:absolute;right:8px;top:8px}.a{display:flex;align-items:flex-end;gap:18px;margin-top:16px;background:#fff;border:1px solid #D9E0E8;border-radius:10px;padding:14px}'
            '.d{background:#14233A;border-radius:10px;padding:10px;margin-top:12px}</style><h1>%s</h1><div class="g">%s</div><div class="a">%s %s %s</div>'
            % (TITLES[style], "".join(cells), app, app_s, app_x))
    write(os.path.join(d, "preview.html"), page)


def main():
    for style in (1, 2, 3):
        d = os.path.join(HERE, NAMES[style])
        os.makedirs(d, exist_ok=True)
        for name, (label, cat, parts) in ICONS.items():
            write(os.path.join(d, name + ".svg"), icon_svg(style, parts, cat))
        write(os.path.join(d, "app-icon.svg"), APP[style])
        preview(style)
    print("ok")


if __name__ == "__main__":
    main()
