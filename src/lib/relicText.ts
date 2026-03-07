const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const openTag = (tag: string) => {
  const t = tag.toLowerCase();
  if (t === "b") return '<strong class="inline-block">';
  if (t === "i") return '<em class="inline-block">';
  if (t === "u") return '<span class="inline-block underline">';
  if (t === "gold") return '<span class="inline-block text-[#ffd38c]">';
  if (t === "red") return '<span class="inline-block text-[#ff7b7b]">';
  if (t === "blue") return '<span class="inline-block text-[#7fb8ff]">';
  if (t === "green") return '<span class="inline-block text-[#86e3a0]">';
  if (t === "purple") return '<span class="inline-block text-[#b89bff]">';
  if (t === "orange") return '<span class="inline-block text-[#ffb46a]">';
  if (t === "aqua") return '<span class="inline-block text-[#7fe3ff]">';
  if (t === "pink") return '<span class="inline-block text-[#ff9bd0]">';
  if (t === "rainbow") {
    return '<span class="inline-block text-transparent [background:linear-gradient(90deg,#ff6b6b,#ffd93d,#6bffb6,#6bc7ff,#b56bff)] [-webkit-background-clip:text]">';
  }
  if (t === "amount")
    return '<span class="inline-block text-[#ffe6b0] font-semibold">';
  if (t === "passive" || t === "evoke")
    return '<span class="inline-block text-[#bfe5ff] uppercase tracking-[0.08em] text-[0.85em]">';
  if (t === "sine") return '<span class="inline-block animate-bounce">';
  if (t === "jitter") return '<span class="inline-block animate-pulse">';
  return '<span class="inline-block">';
};

const closeTag = (tag: string) => {
  const t = tag.toLowerCase();
  if (t === "b") return "</strong>";
  if (t === "i") return "</em>";
  if (t === "u") return "</span>";
  return "</span>";
};

export const formatRelicText = (desc: string, basePath: string) => {
  if (!desc) return "";
  const escaped = escapeHtml(desc);
  return escaped
    .replace(/\[energy:(\d+)\]/gi, (_, raw) => {
      const count = Math.max(0, Math.min(9, Number(raw)));
      if (!count) return "";
      const icon = `${basePath}/images/ui/energy_colorless.png`;
      return `<span class="inline-flex gap-0.5 align-middle">${Array.from({
        length: count,
      })
        .map(
          () =>
            `<img class="inline-block align-text-bottom" style="height:1em;width:1em;margin-bottom:0.1em;filter:drop-shadow(0 1px 1px rgba(0,0,0,0.45));" src="${icon}" alt="" />`,
        )
        .join("")}</span>`;
    })
    .replace(/\[([a-zA-Z0-9_]+)\]([\s\S]*?)\[\/\1\]/g, (_, tag, inner) => {
      return `${openTag(tag)}${inner}${closeTag(tag)}`;
    })
    .replace(/\[([a-zA-Z0-9_]+)\]/g, (_, tag) => openTag(tag))
    .replace(/\[\/([a-zA-Z0-9_]+)\]/g, (_, tag) => closeTag(tag))
    .replace(/\n/g, "<br />");
};
