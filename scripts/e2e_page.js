// Page-side helpers for scripts/e2e_cdp.py, evaluated in the Flutter web
// page (semantics on: tool/e2e/main.dart). A node's label is its
// aria-label, else its own text.
({
  label: (e) => (e.getAttribute('aria-label') || e.textContent || '').trim(),

  nodes: () => [...document.querySelectorAll('flt-semantics, [role], [aria-label]')],

  // The node labelled `label` (else the first whose label starts with it).
  // A container can carry its only child's label: a button wins, then the
  // smallest box. The point is the centre of the node's on-screen part;
  // `visible` is false when none of it is in the viewport (`below`: it is
  // under the fold).
  find(label) {
    const area = (e) => {
      const r = e.getBoundingClientRect();
      return r.width * r.height;
    };
    // A disabled twin (aria-disabled) loses to the enabled one.
    const off = (e) => (e.getAttribute('aria-disabled') === 'true' ? 2e12 : 0);
    const rank = (e) => off(e) + (e.getAttribute('role') === 'button' ? 0 : 1e12) + area(e);
    const best = (list) => list.sort((a, b) => rank(a) - rank(b))[0];
    const all = this.nodes();
    const hit = best(all.filter((e) => this.label(e) === label))
      || best(all.filter((e) => this.label(e).startsWith(label)));
    if (!hit) return null;
    const r = hit.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return null;
    const top = Math.max(r.top, 0), bottom = Math.min(r.bottom, innerHeight);
    const left = Math.max(r.left, 0), right = Math.min(r.right, innerWidth);
    const visible = bottom - top >= 4 && right - left >= 4;
    return {
      x: visible ? (left + right) / 2 : r.x + r.width / 2,
      y: visible ? (top + bottom) / 2 : r.y + r.height / 2,
      visible,
      below: r.top >= innerHeight,
      text: this.label(hit),
    };
  },

  // Every non-empty label on the page, one per line.
  text() {
    return this.nodes().map((e) => this.label(e)).filter((t) => t).join('\n');
  },
})
