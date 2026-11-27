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

  // A node's label and viewport rect.
  rect(e) {
    const r = e.getBoundingClientRect();
    return { text: this.label(e), left: r.left, top: r.top, right: r.right,
      bottom: r.bottom, x: r.x + r.width / 2, y: r.y + r.height / 2, visible: true };
  },

  // Every node labelled `label` (`prefix`: starting with it), innermost
  // only (a container's text starts with its first child's), in document order.
  findAll(label, prefix) {
    const match = (e) => (prefix ? this.label(e).startsWith(label) : this.label(e) === label);
    const hits = this.nodes().filter((e) => this.label(e) && match(e));
    return hits.filter((e) => !hits.some((o) => o !== e && e.contains(o)))
      .map((e) => this.rect(e)).filter((r) => r.right > r.left && r.bottom > r.top);
  },

  // Every labelled node with no labelled node inside it, with its rect.
  leaves() {
    const all = this.nodes().filter((e) => this.label(e));
    return all.filter((e) => !all.some((o) => o !== e && e.contains(o)))
      .map((e) => this.rect(e)).filter((r) => r.right > r.left && r.bottom > r.top);
  },

  // Every non-empty label on the page, one per line.
  text() {
    return this.nodes().map((e) => this.label(e)).filter((t) => t).join('\n');
  },
})
