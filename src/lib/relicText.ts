const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeAttr = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/"/g, "&quot;");

type TextLink = { href: string };
type FormatRelicTextOptions = {
  resolveMention?: (text: string) => TextLink | null;
};

const openTag = (tag: string, arg?: string) => {
  const t = tag.toLowerCase();
  if (t === "b") return '<strong class="inline-block">';
  if (t === "i") return '<em class="inline-block">';
  if (t === "u") return '<span class="inline-block underline">';
  if (t === "font_size") {
    const parsed = Number(arg ?? 0);
    const px = Number.isFinite(parsed)
      ? Math.max(10, Math.min(48, parsed))
      : 16;
    return `<span class="inline-block align-baseline" style="font-size:${px}px;line-height:1.15;">`;
  }
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
  if (t === "link") {
    const href = arg ? escapeAttr(arg) : "#";
    return `<a class="inline-block underline decoration-dotted underline-offset-2 hover:text-[#fff5df] transition-colors" href="${href}">`;
  }
  return '<span class="inline-block">';
};

const closeTag = (tag: string) => {
  const t = tag.toLowerCase();
  if (t === "b") return "</strong>";
  if (t === "i") return "</em>";
  if (t === "u") return "</span>";
  if (t === "link") return "</a>";
  return "</span>";
};

export const formatRelicText = (
  desc: string,
  basePath: string,
  options?: FormatRelicTextOptions,
) => {
  if (!desc) return "";
  const withMentions =
    options?.resolveMention
      ? desc.replace(
          /\[(gold|aqua|blue|green|purple|orange|red|pink)\]([\s\S]*?)\[\/\1\]/gi,
          (full, color, inner) => {
            const content = String(inner ?? "");
            if (!content.trim() || content.includes("[") || content.includes("\n")) {
              return full;
            }
            const linked = options.resolveMention?.(content.trim());
            if (!linked?.href) return full;
            return `[${color}][link=${linked.href}]${content}[/link][/${color}]`;
          },
        )
      : desc;
  const escaped = escapeHtml(withMentions);
  return escaped
    .replace(/\[(passive|evoke)\]/gi, (_, key) => {
      const label = String(key).toUpperCase();
      return `<span class="inline-block text-[#bfe5ff] uppercase tracking-[0.08em] text-[0.85em]">${label}</span>`;
    })
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
    .replace(/\[star:(\d+)\]/gi, (_, raw) => {
      const count = Math.max(0, Math.min(9, Number(raw)));
      if (!count) return "";
      const icon = `${basePath}/images/icons/star_icon.png`;
      return `<span class="inline-flex gap-0.5 align-middle">${Array.from({
        length: count,
      })
        .map(
          () =>
            `<img class="inline-block align-text-bottom" style="height:1em;width:1em;margin-bottom:0.1em;filter:drop-shadow(0 1px 1px rgba(0,0,0,0.45));" src="${icon}" alt="" />`,
        )
        .join("")}</span>`;
    })
    .replace(
      /\[([a-zA-Z0-9_]+)(?:=([^\]]+))?\]([\s\S]*?)\[\/\1\]/g,
      (_, tag, arg, inner) => {
        return `${openTag(tag, arg)}${inner}${closeTag(tag)}`;
      },
    )
    .replace(/\[([a-zA-Z0-9_]+)(?:=([^\]]+))?\]/g, (_, tag, arg) => {
      return openTag(tag, arg);
    })
    .replace(/\[\/([a-zA-Z0-9_]+)\]/g, (_, tag) => closeTag(tag))
    .replace(/\n/g, "<br />");
};
